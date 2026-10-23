package com.example.fastcontacts

import android.content.Context
import android.provider.CallLog
import android.text.format.DateFormat
import android.text.format.DateUtils
import android.transition.AutoTransition
import android.transition.TransitionManager
import android.view.Gravity
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.HorizontalScrollView
import android.widget.ImageButton
import android.widget.ImageView
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import androidx.recyclerview.widget.DiffUtil
import androidx.recyclerview.widget.ListAdapter
import androidx.recyclerview.widget.RecyclerView
import com.google.android.material.bottomsheet.BottomSheetDialog
import java.util.Date

/** A small read-only model of a recent call. */
data class CallLogEntry(
    val name: String,
    val number: String,
    val dateMillis: Long,
    val type: Int,
    val durationSeconds: Long,
    val label: String = ""
)

/** Compares phone numbers by their last digits so +880 1855... and 01855... are the same person. */
object PhoneKey {
    fun of(number: String): String {
        val d = number.filter { it.isDigit() }
        return if (d.length > 8) d.takeLast(8) else d
    }
}

/** Finds which saved contact owns a phone number (built once per contact load). */
class PhoneIndex(contacts: List<Contact>) {
    class Match(val contact: Contact, val phone: Phone)

    private val map = HashMap<String, Match>()

    init {
        for (c in contacts) {
            for (p in c.phones) {
                val k = PhoneKey.of(p.number)
                if (k.isNotEmpty() && !map.containsKey(k)) map[k] = Match(c, p)
            }
        }
    }

    fun find(number: String): Match? {
        val k = PhoneKey.of(number)
        return if (k.isEmpty()) null else map[k]
    }
}

object CallLogRepository {
    fun loadRecent(context: Context, limit: Int): List<CallLogEntry> {
        return try {
            query(context, limit, true)
        } catch (_: SecurityException) {
            // The user may deny call-log access; Contacts and Dialpad still work.
            emptyList()
        } catch (_: IllegalArgumentException) {
            try {
                query(context, limit, false)
            } catch (_: Exception) {
                emptyList()
            }
        }
    }

    /** Calls that belong to any of the given PhoneKey values, newest first. */
    fun loadForKeys(context: Context, keys: Set<String>, max: Int): List<CallLogEntry> {
        if (keys.isEmpty()) return emptyList()
        return loadRecent(context, 1500).filter { PhoneKey.of(it.number) in keys }.take(max)
    }

    private fun query(context: Context, limit: Int, withLabel: Boolean): List<CallLogEntry> {
        val result = ArrayList<CallLogEntry>()
        val projection = if (withLabel) {
            arrayOf(
                CallLog.Calls.CACHED_NAME,
                CallLog.Calls.NUMBER,
                CallLog.Calls.DATE,
                CallLog.Calls.TYPE,
                CallLog.Calls.DURATION,
                CallLog.Calls.CACHED_NUMBER_LABEL
            )
        } else {
            arrayOf(
                CallLog.Calls.CACHED_NAME,
                CallLog.Calls.NUMBER,
                CallLog.Calls.DATE,
                CallLog.Calls.TYPE,
                CallLog.Calls.DURATION
            )
        }
        context.contentResolver.query(
            CallLog.Calls.CONTENT_URI,
            projection,
            null,
            null,
            "${CallLog.Calls.DATE} DESC"
        )?.use { cursor ->
            val nameCol = cursor.getColumnIndex(CallLog.Calls.CACHED_NAME)
            val numberCol = cursor.getColumnIndex(CallLog.Calls.NUMBER)
            val dateCol = cursor.getColumnIndex(CallLog.Calls.DATE)
            val typeCol = cursor.getColumnIndex(CallLog.Calls.TYPE)
            val durationCol = cursor.getColumnIndex(CallLog.Calls.DURATION)
            val labelCol = cursor.getColumnIndex(CallLog.Calls.CACHED_NUMBER_LABEL)
            while (cursor.moveToNext() && result.size < limit) {
                val number = if (numberCol >= 0) cursor.getString(numberCol).orEmpty() else ""
                val name = if (nameCol >= 0) cursor.getString(nameCol).orEmpty() else ""
                val date = if (dateCol >= 0) cursor.getLong(dateCol) else 0L
                val type = if (typeCol >= 0) cursor.getInt(typeCol) else CallLog.Calls.MISSED_TYPE
                val duration = if (durationCol >= 0) cursor.getLong(durationCol) else 0L
                val label = if (withLabel && labelCol >= 0) cursor.getString(labelCol).orEmpty() else ""
                if (number.isNotBlank()) {
                    result.add(CallLogEntry(name.ifBlank { number }, number, date, type, duration, label))
                }
            }
        }
        return result
    }
}

object CallTypes {
    class Info(val label: String, val colorRes: Int, val arrow: String)

    fun info(type: Int): Info = when (type) {
        CallLog.Calls.OUTGOING_TYPE -> Info("Outgoing", R.color.app_text_secondary, "↗")
        CallLog.Calls.INCOMING_TYPE -> Info("Incoming", R.color.app_text_secondary, "↙")
        CallLog.Calls.MISSED_TYPE -> Info("Missed", R.color.app_danger, "↙")
        CallLog.Calls.REJECTED_TYPE -> Info("Rejected", R.color.app_danger, "✗")
        CallLog.Calls.BLOCKED_TYPE -> Info("Blocked", R.color.app_text_secondary, "⊘")
        else -> Info("Call", R.color.app_text_secondary, "•")
    }

    fun isMissed(type: Int): Boolean =
        type == CallLog.Calls.MISSED_TYPE || type == CallLog.Calls.REJECTED_TYPE
}

/** Consecutive calls with the same person and the same type, shown as one row. */
data class CallGroup(
    val key: String,
    val name: String,
    val number: String,
    val type: Int,
    val label: String,
    val calls: List<CallLogEntry>,
    val contact: Contact?
)

sealed class HomeRow {
    data class Favourites(val contacts: List<Contact>) : HomeRow()
    data class Day(val title: String) : HomeRow()
    data class Call(val group: CallGroup) : HomeRow()
    data class Notice(val text: String) : HomeRow()
}

object HomeBuilder {

    fun groups(entries: List<CallLogEntry>, index: PhoneIndex?): List<CallGroup> {
        val out = ArrayList<CallGroup>()
        var i = 0
        while (i < entries.size) {
            val first = entries[i]
            val k = PhoneKey.of(first.number)
            var j = i + 1
            while (j < entries.size && entries[j].type == first.type && PhoneKey.of(entries[j].number) == k) j++
            val calls = entries.subList(i, j).toList()
            val match = index?.find(first.number)
            val name = match?.contact?.name?.ifBlank { first.name } ?: first.name
            val label = match?.phone?.type?.takeIf { it.isNotBlank() } ?: first.label
            out.add(
                CallGroup(
                    key = first.number + "|" + first.type + "|" + first.dateMillis,
                    name = name,
                    number = first.number,
                    type = first.type,
                    label = label,
                    calls = calls,
                    contact = match?.contact
                )
            )
            i = j
        }
        return out
    }

    fun rows(ctx: Context, groups: List<CallGroup>, favourites: List<Contact>, notice: String?): List<HomeRow> {
        val out = ArrayList<HomeRow>()
        out.add(HomeRow.Favourites(favourites))
        if (notice != null) {
            out.add(HomeRow.Notice(notice))
            return out
        }
        var lastDay = ""
        for (g in groups) {
            val day = dayTitle(ctx, g.calls[0].dateMillis)
            if (day != lastDay) {
                out.add(HomeRow.Day(day))
                lastDay = day
            }
            out.add(HomeRow.Call(g))
        }
        return out
    }

    fun dayTitle(ctx: Context, ms: Long): String {
        if (ms <= 0L) return "Earlier"
        if (DateUtils.isToday(ms)) return "Today"
        if (DateUtils.isToday(ms + DateUtils.DAY_IN_MILLIS)) return "Yesterday"
        return DateUtils.formatDateTime(
            ctx, ms,
            DateUtils.FORMAT_SHOW_DATE or DateUtils.FORMAT_SHOW_WEEKDAY or DateUtils.FORMAT_ABBREV_ALL
        )
    }

    fun time(ctx: Context, ms: Long): String = DateFormat.getTimeFormat(ctx).format(Date(ms))

    fun shortAgo(ctx: Context, ms: Long): String {
        if (ms <= 0L) return ""
        val diff = System.currentTimeMillis() - ms
        return when {
            diff in 0L..59_999L -> "Just now"
            diff in 60_000L..3_599_999L -> DateUtils.getRelativeTimeSpanString(
                ms, System.currentTimeMillis(), DateUtils.MINUTE_IN_MILLIS, DateUtils.FORMAT_ABBREV_RELATIVE
            ).toString()
            else -> time(ctx, ms)
        }
    }

    fun duration(seconds: Long): String {
        if (seconds <= 0L) return ""
        val h = seconds / 3600
        val m = (seconds % 3600) / 60
        val s = seconds % 60
        return when {
            h > 0 -> "${h}h ${m}m"
            m > 0 -> "${m}m ${s}s"
            else -> "${s}s"
        }
    }
}

/** Bottom sheet listing every call with one person. */
object CallHistorySheet {
    fun show(ctx: Context, title: String, entries: List<CallLogEntry>) {
        val dialog = BottomSheetDialog(ctx)
        val scroll = ScrollView(ctx)
        val root = LinearLayout(ctx)
        root.orientation = LinearLayout.VERTICAL
        root.setPadding(0, Ui.dp(ctx, 8), 0, Ui.dp(ctx, 20))
        scroll.addView(root)

        val t = TextView(ctx)
        t.text = title
        t.textSize = 18f
        t.setTypeface(null, android.graphics.Typeface.BOLD)
        t.setTextColor(Ui.color(ctx, R.color.app_text))
        t.setPadding(Ui.dp(ctx, 24), Ui.dp(ctx, 12), Ui.dp(ctx, 24), Ui.dp(ctx, 4))
        root.addView(t)

        val sub = TextView(ctx)
        sub.text = "Call history"
        sub.textSize = 13f
        sub.setTextColor(Ui.color(ctx, R.color.app_text_secondary))
        sub.setPadding(Ui.dp(ctx, 24), 0, Ui.dp(ctx, 24), Ui.dp(ctx, 8))
        root.addView(sub)

        if (entries.isEmpty()) {
            val empty = TextView(ctx)
            empty.text = "No calls found"
            empty.textSize = 14f
            empty.setTextColor(Ui.color(ctx, R.color.app_text_secondary))
            empty.setPadding(Ui.dp(ctx, 24), Ui.dp(ctx, 16), Ui.dp(ctx, 24), Ui.dp(ctx, 16))
            root.addView(empty)
        }

        for (e in entries) {
            val info = CallTypes.info(e.type)
            val color = Ui.color(ctx, info.colorRes)
            val row = LinearLayout(ctx)
            row.orientation = LinearLayout.HORIZONTAL
            row.gravity = Gravity.CENTER_VERTICAL
            row.minimumHeight = Ui.dp(ctx, 56)
            row.setPadding(Ui.dp(ctx, 24), Ui.dp(ctx, 6), Ui.dp(ctx, 24), Ui.dp(ctx, 6))

            val arrow = TextView(ctx)
            arrow.text = info.arrow
            arrow.textSize = 16f
            arrow.setTextColor(color)
            arrow.gravity = Gravity.CENTER
            row.addView(arrow, LinearLayout.LayoutParams(Ui.dp(ctx, 32), ViewGroup.LayoutParams.WRAP_CONTENT))

            val col = LinearLayout(ctx)
            col.orientation = LinearLayout.VERTICAL
            val p = TextView(ctx)
            p.text = info.label
            p.textSize = 16f
            p.setTextColor(if (CallTypes.isMissed(e.type)) color else Ui.color(ctx, R.color.app_text))
            col.addView(p)
            val s = TextView(ctx)
            val day = HomeBuilder.dayTitle(ctx, e.dateMillis)
            s.text = day + " · " + HomeBuilder.time(ctx, e.dateMillis)
            s.textSize = 13f
            s.setTextColor(Ui.color(ctx, R.color.app_text_secondary))
            col.addView(s)
            row.addView(col, LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f))

            val d = HomeBuilder.duration(e.durationSeconds)
            if (d.isNotEmpty()) {
                val dv = TextView(ctx)
                dv.text = d
                dv.textSize = 13f
                dv.setTextColor(Ui.color(ctx, R.color.app_text_secondary))
                row.addView(dv)
            }
            root.addView(row)
        }

        dialog.setContentView(scroll)
        dialog.show()
    }
}

/**
 * Home / Recents list: Favourites strip, day headers and grouped call rows.
 * Tap the avatar = open contact; tap the row = expand the inline drawer.
 */
class HomeAdapter(
    private val onAvatar: (CallGroup) -> Unit,
    private val onCall: (CallGroup) -> Unit,
    private val onMessage: (CallGroup) -> Unit,
    private val onHistory: (CallGroup) -> Unit,
    private val onFavourite: (Contact) -> Unit,
    private val onAddFavourite: () -> Unit,
    private val onNotice: () -> Unit
) : ListAdapter<HomeRow, RecyclerView.ViewHolder>(Diff()) {

    private class Diff : DiffUtil.ItemCallback<HomeRow>() {
        override fun areItemsTheSame(a: HomeRow, b: HomeRow): Boolean = when {
            a is HomeRow.Favourites && b is HomeRow.Favourites -> true
            a is HomeRow.Day && b is HomeRow.Day -> a.title == b.title
            a is HomeRow.Call && b is HomeRow.Call -> a.group.key == b.group.key
            a is HomeRow.Notice && b is HomeRow.Notice -> true
            else -> false
        }

        override fun areContentsTheSame(a: HomeRow, b: HomeRow): Boolean = a == b
    }

    private var expandedKey: String? = null
    private var favCollapsed = false
    private var recycler: RecyclerView? = null

    fun submit(rows: List<HomeRow>) {
        submitList(rows)
    }

    override fun onAttachedToRecyclerView(recyclerView: RecyclerView) {
        super.onAttachedToRecyclerView(recyclerView)
        recycler = recyclerView
    }

    override fun onDetachedFromRecyclerView(recyclerView: RecyclerView) {
        super.onDetachedFromRecyclerView(recyclerView)
        recycler = null
    }

    override fun getItemViewType(position: Int): Int = when (getItem(position)) {
        is HomeRow.Favourites -> 0
        is HomeRow.Day -> 1
        is HomeRow.Call -> 2
        is HomeRow.Notice -> 3
    }

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): RecyclerView.ViewHolder {
        val inf = LayoutInflater.from(parent.context)
        return when (viewType) {
            0 -> FavVH(inf.inflate(R.layout.item_home_favourites, parent, false))
            1 -> DayVH(inf.inflate(R.layout.item_call_day, parent, false))
            2 -> CallVH(inf.inflate(R.layout.item_call_log, parent, false))
            else -> NoticeVH(inf.inflate(R.layout.item_notice, parent, false))
        }
    }

    override fun onBindViewHolder(holder: RecyclerView.ViewHolder, position: Int) {
        val row = getItem(position)
        when {
            holder is FavVH && row is HomeRow.Favourites -> holder.bind(row.contacts)
            holder is DayVH && row is HomeRow.Day -> holder.text.text = row.title
            holder is CallVH && row is HomeRow.Call -> holder.bind(row.group)
            holder is NoticeVH && row is HomeRow.Notice -> {
                holder.text.text = row.text
                holder.text.setOnClickListener { onNotice() }
            }
        }
    }

    override fun onBindViewHolder(
        holder: RecyclerView.ViewHolder,
        position: Int,
        payloads: MutableList<Any>
    ) {
        if (payloads.isNotEmpty() && holder is CallVH) {
            val row = getItem(position)
            if (row is HomeRow.Call) holder.applyExpanded(row.group, row.group.key == expandedKey)
            return
        }
        super.onBindViewHolder(holder, position, payloads)
    }

    private fun toggle(key: String) {
        val old = expandedKey
        expandedKey = if (old == key) null else key
        recycler?.let { TransitionManager.beginDelayedTransition(it, AutoTransition().setDuration(180L)) }
        for (i in 0 until itemCount) {
            val r = getItem(i)
            if (r is HomeRow.Call && (r.group.key == old || r.group.key == key)) {
                notifyItemChanged(i, "expand")
            }
        }
    }

    inner class FavVH(view: View) : RecyclerView.ViewHolder(view) {
        private val header: View = view.findViewById(R.id.favHeader)
        private val chevron: ImageView = view.findViewById(R.id.favChevron)
        private val scroll: HorizontalScrollView = view.findViewById(R.id.favScroll)
        private val row: LinearLayout = view.findViewById(R.id.favRow)

        fun bind(list: List<Contact>) {
            val ctx = itemView.context
            chevron.rotation = if (favCollapsed) 0f else 180f
            scroll.visibility = if (favCollapsed) View.GONE else View.VISIBLE
            header.setOnClickListener {
                favCollapsed = !favCollapsed
                recycler?.let { TransitionManager.beginDelayedTransition(it, AutoTransition().setDuration(180L)) }
                scroll.visibility = if (favCollapsed) View.GONE else View.VISIBLE
                chevron.animate().rotation(if (favCollapsed) 0f else 180f).setDuration(180L).start()
            }
            row.removeAllViews()
            val inf = LayoutInflater.from(ctx)

            val add = inf.inflate(R.layout.item_favourite, row, false)
            add.findViewById<View>(R.id.favAvatar).visibility = View.GONE
            add.findViewById<View>(R.id.favAddIcon).visibility = View.VISIBLE
            add.findViewById<TextView>(R.id.favName).text = "Add"
            add.contentDescription = "Add favourite"
            add.setOnClickListener { onAddFavourite() }
            row.addView(add)

            for (c in list) {
                val v = inf.inflate(R.layout.item_favourite, row, false)
                v.findViewById<AvatarView>(R.id.favAvatar).bind(c)
                v.findViewById<TextView>(R.id.favName).text = c.firstName.ifBlank { c.name }
                v.contentDescription = c.name
                v.setOnClickListener { onFavourite(c) }
                row.addView(v)
            }
        }
    }

    class DayVH(view: View) : RecyclerView.ViewHolder(view) {
        val text: TextView = view.findViewById(R.id.dayText)
    }

    class NoticeVH(view: View) : RecyclerView.ViewHolder(view) {
        val text: TextView = view.findViewById(R.id.noticeText)
    }

    inner class CallVH(view: View) : RecyclerView.ViewHolder(view) {
        private val callRow: View = view.findViewById(R.id.callRow)
        private val avatar: AvatarView = view.findViewById(R.id.callAvatar)
        private val name: TextView = view.findViewById(R.id.callName)
        private val number: TextView = view.findViewById(R.id.callNumber)
        private val meta: TextView = view.findViewById(R.id.callMeta)
        private val typeIcon: TextView = view.findViewById(R.id.callTypeIcon)
        private val callBtn: ImageButton = view.findViewById(R.id.callBtn)
        private val expanded: View = view.findViewById(R.id.callExpanded)
        private val times: LinearLayout = view.findViewById(R.id.callTimes)
        private val seeMore: View = view.findViewById(R.id.callSeeMore)
        private val message: View = view.findViewById(R.id.callMessage)
        private val history: View = view.findViewById(R.id.callHistory)

        fun bind(g: CallGroup) {
            val ctx = itemView.context
            val info = CallTypes.info(g.type)
            val color = Ui.color(ctx, info.colorRes)
            val count = g.calls.size

            val shown = if (count > 1) {
                val base = if (g.name.length > 20) g.name.take(19).trimEnd() + "…" else g.name
                "$base ($count)"
            } else g.name
            name.text = shown

            if (g.name != g.number && g.number.isNotBlank()) {
                number.text = g.number
                number.visibility = View.VISIBLE
            } else {
                number.visibility = View.GONE
            }

            val c = g.contact
            if (c != null) avatar.bind(c) else avatar.bindPlain(g.name, null)

            typeIcon.text = info.arrow
            typeIcon.setTextColor(color)
            meta.setTextColor(color)
            val ago = HomeBuilder.shortAgo(ctx, g.calls[0].dateMillis)
            meta.text = listOf(g.label, ago).filter { it.isNotBlank() }.joinToString(" • ")

            callRow.contentDescription = g.name + ", " + info.label + ", tap to show details"
            avatar.setOnClickListener { onAvatar(g) }
            callRow.setOnClickListener { toggle(g.key) }
            callBtn.setOnClickListener { onCall(g) }
            message.setOnClickListener { onMessage(g) }
            history.setOnClickListener { onHistory(g) }
            seeMore.setOnClickListener { onHistory(g) }

            applyExpanded(g, g.key == expandedKey)
        }

        fun applyExpanded(g: CallGroup, open: Boolean) {
            val ctx = itemView.context
            expanded.visibility = if (open) View.VISIBLE else View.GONE
            if (!open) return
            times.removeAllViews()
            val firstDay = HomeBuilder.dayTitle(ctx, g.calls[0].dateMillis)
            val extra = g.calls.drop(1)
            for (e in extra) {
                val tv = TextView(ctx)
                val day = HomeBuilder.dayTitle(ctx, e.dateMillis)
                tv.text = if (day == firstDay) HomeBuilder.time(ctx, e.dateMillis)
                else day + ", " + HomeBuilder.time(ctx, e.dateMillis)
                tv.textSize = 15f
                tv.setTextColor(Ui.color(ctx, R.color.app_text))
                tv.setPadding(0, Ui.dp(ctx, 6), 0, Ui.dp(ctx, 6))
                times.addView(tv)
            }
            times.visibility = if (extra.isEmpty()) View.GONE else View.VISIBLE
            seeMore.visibility = if (extra.isEmpty()) View.GONE else View.VISIBLE
        }
    }
}
