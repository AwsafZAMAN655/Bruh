"""
upgrade_md3.py - FastContacts Material 3 (Google Phone style) upgrade.

HOW TO RUN (Windows CMD):
  1. Save this file inside your FastContacts project folder
     (the folder that contains the "app" folder).
  2. Open CMD in that folder and run:   python upgrade_md3.py
  3. Commit and push to GitHub, then run the "Build FastContacts APK" action.

It rewrites the UI files only. Contacts Provider sync, search index, vCard
import/export, labels and quick actions are NOT touched.
To undo everything:   git restore .   (then delete the new files with: git clean -fd)
"""
import os
import sys

FILES = {}
FILES['app/src/main/java/com/example/fastcontacts/AvatarView.kt'] = r'''package com.example.fastcontacts

import android.content.Context
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.BitmapShader
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Matrix
import android.graphics.Paint
import android.graphics.Shader
import android.graphics.Typeface
import android.net.Uri
import android.util.AttributeSet
import android.util.LruCache
import android.view.View
import java.io.ByteArrayOutputStream
import kotlin.math.max
import kotlin.math.min

object Avatar {
    private val colors = intArrayOf(
        0xFFFDD663.toInt(), 0xFFF6AEA9.toInt(), 0xFFF3A8DB.toInt(), 0xFFA8DAB5.toInt(),
        0xFF73D7F3.toInt(), 0xFFD7AEFB.toInt(), 0xFFAECBFA.toInt(), 0xFFFDC69C.toInt()
    )

    fun letter(name: String): String = name.trim().firstOrNull()?.uppercase() ?: "?"

    fun colorFor(name: String): Int = colors[(name.hashCode() and 0x7fffffff) % colors.size]
}

object Photos {
    private val cache = object : LruCache<String, Bitmap>(8 * 1024 * 1024) {
        override fun sizeOf(key: String, value: Bitmap): Int = value.byteCount
    }

    fun load(ctx: Context, uri: String?): Bitmap? {
        if (uri.isNullOrEmpty()) return null
        cache.get(uri)?.let { return it }
        return try {
            ctx.contentResolver.openInputStream(Uri.parse(uri))?.use {
                val b = BitmapFactory.decodeStream(it)
                if (b != null) cache.put(uri, b)
                b
            }
        } catch (e: Exception) {
            null
        }
    }

    fun decodeSquare(ctx: Context, uri: Uri, size: Int): Bitmap? {
        return try {
            val cr = ctx.contentResolver
            val o = BitmapFactory.Options()
            o.inJustDecodeBounds = true
            cr.openInputStream(uri)?.use { BitmapFactory.decodeStream(it, null, o) }
            var s = 1
            while (o.outWidth / (s * 2) >= size && o.outHeight / (s * 2) >= size) s *= 2
            val o2 = BitmapFactory.Options()
            o2.inSampleSize = s
            val bmp = cr.openInputStream(uri)?.use { BitmapFactory.decodeStream(it, null, o2) } ?: return null
            val side = min(bmp.width, bmp.height)
            val sq = Bitmap.createBitmap(bmp, (bmp.width - side) / 2, (bmp.height - side) / 2, side, side)
            Bitmap.createScaledBitmap(sq, size, size, true)
        } catch (e: Exception) {
            null
        }
    }

    fun toJpeg(b: Bitmap): ByteArray {
        val out = ByteArrayOutputStream()
        b.compress(Bitmap.CompressFormat.JPEG, 90, out)
        return out.toByteArray()
    }
}

class AvatarView @JvmOverloads constructor(context: Context, attrs: AttributeSet? = null) :
    View(context, attrs) {

    private val bg = Paint(Paint.ANTI_ALIAS_FLAG)
    private val txt = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        color = 0xFF1F2423.toInt()
        textAlign = Paint.Align.CENTER
        typeface = Typeface.DEFAULT_BOLD
    }
    private val photoPaint = Paint(Paint.ANTI_ALIAS_FLAG or Paint.FILTER_BITMAP_FLAG)
    private var letter = "?"
    private var bitmap: Bitmap? = null

    fun bind(c: Contact, full: Boolean = false) {
        bindPlain(c.name, Photos.load(context, if (full) (c.photoFull ?: c.photoThumb) else c.photoThumb))
    }

    fun bindPlain(name: String, bmp: Bitmap?) {
        letter = Avatar.letter(name)
        bg.color = Avatar.colorFor(name)
        bitmap = bmp
        contentDescription = name
        rebuild()
        invalidate()
    }

    fun setPhotoBitmap(bmp: Bitmap?) {
        bitmap = bmp
        rebuild()
        invalidate()
    }

    override fun onSizeChanged(w: Int, h: Int, oldw: Int, oldh: Int) {
        super.onSizeChanged(w, h, oldw, oldh)
        rebuild()
    }

    private fun rebuild() {
        val bmp = bitmap
        if (bmp == null || width == 0 || height == 0) {
            photoPaint.shader = null
            return
        }
        val shader = BitmapShader(bmp, Shader.TileMode.CLAMP, Shader.TileMode.CLAMP)
        val scale = max(width.toFloat() / bmp.width, height.toFloat() / bmp.height)
        val m = Matrix()
        m.setScale(scale, scale)
        m.postTranslate((width - bmp.width * scale) / 2f, (height - bmp.height * scale) / 2f)
        shader.setLocalMatrix(m)
        photoPaint.shader = shader
    }

    override fun onDraw(canvas: Canvas) {
        val cx = width / 2f
        val cy = height / 2f
        val r = min(width, height) / 2f
        if (bitmap != null && photoPaint.shader != null) {
            canvas.drawCircle(cx, cy, r, photoPaint)
        } else {
            canvas.drawCircle(cx, cy, r, bg)
            txt.textSize = r * 0.9f
            val y = cy - (txt.descent() + txt.ascent()) / 2f
            canvas.drawText(letter, cx, y, txt)
        }
    }
}
'''

FILES['app/src/main/java/com/example/fastcontacts/CallLogAdapter.kt'] = r'''package com.example.fastcontacts

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
'''

FILES['app/src/main/java/com/example/fastcontacts/DetailActivity.kt'] = r'''package com.example.fastcontacts

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Bundle
import android.transition.TransitionManager
import android.view.Gravity
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.Button
import android.widget.EditText
import android.widget.GridLayout
import android.widget.HorizontalScrollView
import android.widget.ImageButton
import android.widget.ImageView
import android.widget.LinearLayout
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat

class DetailActivity : AppCompatActivity() {

    private var contactId = -1L
    private var contact: Contact? = null
    private var groups: List<ContactGroup> = emptyList()
    private lateinit var content: LinearLayout
    private lateinit var btnFav: ImageButton
    private var moreOpen = false

    // WhatsApp UI Elements
    private var whatsappSection: LinearLayout? = null
    private var whatsappHeader: LinearLayout? = null
    private var whatsappActionsContainer: LinearLayout? = null
    private var whatsappExpandIcon: ImageView? = null
    private var isWhatsappExpanded = false

    private class Pill(
        val label: String,
        val icon: Int,
        val tinted: Boolean,
        val enabled: Boolean = true,
        val run: () -> Unit
    )

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_detail)
        Ui.systemBars(this)
        contactId = intent.getLongExtra("contact_id", -1L)
        content = findViewById(R.id.detailContent)
        btnFav = findViewById(R.id.btnFav)

        // Find static WhatsApp views from activity_detail.xml
        whatsappSection = findViewById(R.id.whatsappSection)
        whatsappHeader = findViewById(R.id.whatsappHeader)
        whatsappActionsContainer = findViewById(R.id.whatsappActionsContainer)
        whatsappExpandIcon = findViewById(R.id.whatsappExpandIcon)

        findViewById<ImageButton>(R.id.btnBack).setOnClickListener { finish() }
        btnFav.setOnClickListener {
            contact?.let { c ->
                Ui.pop(btnFav)
                Actions.toggleStar(this, c)
                load()
            }
        }
        findViewById<ImageButton>(R.id.btnEdit).setOnClickListener { contact?.let { Actions.edit(this, it) } }
        findViewById<ImageButton>(R.id.btnMore).setOnClickListener { contact?.let { showMore(it) } }
    }

    override fun onResume() {
        super.onResume()
        load()
    }

    override fun finish() {
        super.finish()
        overridePendingTransition(R.anim.fade_in_soft, R.anim.slide_down_out)
    }

    private fun dp(v: Int): Int = Ui.dp(this, v)

    private fun load() {
        Thread {
            val c = ContactsRepository.loadById(this, contactId)
            val g = ContactsRepository.loadGroups(this)
            runOnUiThread {
                if (c == null) {
                    finish()
                } else {
                    contact = c
                    groups = g
                    bind(c)
                }
            }
        }.start()
    }

    private fun bind(c: Contact) {
        content.removeAllViews()

        btnFav.setImageResource(if (c.starred) R.drawable.ic_star else R.drawable.ic_star_border)
        btnFav.imageTintList = Ui.tint(this, if (c.starred) R.color.app_star else R.color.app_text_secondary)
        btnFav.contentDescription = if (c.starred) "Remove from favorites" else "Add to favorites"

        // ----- header -----
        val header = LinearLayout(this)
        header.orientation = LinearLayout.VERTICAL
        header.gravity = Gravity.CENTER_HORIZONTAL
        header.setPadding(dp(16), dp(0), dp(16), dp(16))
        val av = AvatarView(this)
        av.layoutParams = LinearLayout.LayoutParams(dp(150), dp(150))
        av.bind(c, true)
        header.addView(av)
        val name = TextView(this)
        name.text = c.name
        name.textSize = 30f
        name.gravity = Gravity.CENTER
        name.setTextColor(Ui.color(this, R.color.app_text))
        name.setPadding(0, dp(16), 0, 0)
        header.addView(name)
        val sub = when {
            c.jobTitle.isNotEmpty() && c.company.isNotEmpty() -> c.jobTitle + " at " + c.company
            c.company.isNotEmpty() -> c.company
            c.jobTitle.isNotEmpty() -> c.jobTitle
            else -> ""
        }
        if (sub.isNotEmpty()) {
            val s = TextView(this)
            s.text = sub
            s.textSize = 15f
            s.gravity = Gravity.CENTER
            s.setTextColor(Ui.color(this, R.color.app_text_secondary))
            header.addView(s)
        }
        content.addView(header)

        // ----- quick actions -----
        val pills = ArrayList<Pill>()
        if (c.phones.isNotEmpty()) {
            pills.add(Pill("Call", R.drawable.ic_call, true) {
                Actions.withNumber(this, c) { n -> Actions.call(this, n) }
            })
            pills.add(Pill("Message", R.drawable.ic_sms, true) {
                Actions.withNumber(this, c) { n -> Actions.sms(this, n) }
            })
            pills.add(Pill("Video", R.drawable.ic_video, true) {
                Actions.withNumber(this, c) { n -> Actions.videoCall(this, n) }
            })
        }
        pills.add(Pill("Email", R.drawable.ic_email, true, c.emails.isNotEmpty()) {
            Actions.withEmail(this, c) { e -> Actions.email(this, e) }
        })
        if (c.phones.isNotEmpty() && Actions.isInstalled(this, Social.whatsapp)) {
            pills.add(Pill("WhatsApp", R.drawable.ic_whatsapp_placeholder, false) {
                Actions.withNumber(this, c) { n -> Actions.openSocial(this, Social.whatsapp, n) }
            })
        }
        if (c.addresses.isNotEmpty()) {
            pills.add(Pill("Directions", R.drawable.ic_location, true) {
                Actions.directions(this, c.addresses[0].value)
            })
        }
        pills.add(Pill("Share", R.drawable.ic_share, true) { Actions.share(this, c) })

        val scroll = HorizontalScrollView(this)
        scroll.isHorizontalScrollBarEnabled = false
        val pillRow = LinearLayout(this)
        pillRow.orientation = LinearLayout.HORIZONTAL
        pillRow.setPadding(dp(12), dp(4), dp(12), dp(8))
        for (p in pills) {
            val v = LayoutInflater.from(this).inflate(R.layout.view_action_pill, pillRow, false)
            val icon = v.findViewById<ImageView>(R.id.pillIcon)
            icon.setImageResource(p.icon)
            if (p.tinted) icon.imageTintList = Ui.tint(this, R.color.app_on_accent_container)
            v.findViewById<TextView>(R.id.pillLabel).text = p.label
            v.setOnClickListener { p.run() }
            v.alpha = if (p.enabled) 1f else 0.45f
            val lp = LinearLayout.LayoutParams(dp(76), ViewGroup.LayoutParams.WRAP_CONTENT)
            lp.setMargins(dp(4), 0, dp(4), 0)
            pillRow.addView(v, lp)
        }
        scroll.addView(pillRow)
        content.addView(scroll)

        // ----- phone numbers -----
        if (c.phones.isNotEmpty()) {
            val card = Ui.card(this, content, "Phone")
            val wa = Actions.isInstalled(this, Social.whatsapp)
            for ((i, p) in c.phones.withIndex()) {
                val trailing = ArrayList<Ui.Trail>()
                trailing.add(Ui.Trail(R.drawable.ic_video, "Video call " + p.number) { Actions.videoCall(this, p.number) })
                trailing.add(Ui.Trail(R.drawable.ic_sms, "Message " + p.number) { Actions.sms(this, p.number) })
                if (wa) {
                    trailing.add(Ui.Trail(R.drawable.ic_whatsapp_placeholder, "WhatsApp " + p.number, false) {
                        Actions.openSocial(this, Social.whatsapp, p.number)
                    })
                }
                Ui.row(
                    this, card, if (i == 0) R.drawable.ic_call else null, p.number, p.type,
                    onClick = { Actions.call(this, p.number) },
                    onLong = {
                        Actions.copy(this, p.number)
                        Actions.toast(this, "Number copied")
                    },
                    trailing = trailing
                )
            }
        }

        // ----- recent activity (call history with this contact) -----
        if (c.phones.isNotEmpty() && hasCallLogAccess()) {
            val activityCard = Ui.card(this, content, "Recent activity")
            activityCard.visibility = View.GONE
            val keys = c.phones.map { PhoneKey.of(it.number) }.filter { it.isNotEmpty() }.toSet()
            Thread {
                val calls = CallLogRepository.loadForKeys(this, keys, 5)
                runOnUiThread {
                    if (isFinishing || isDestroyed || calls.isEmpty()) return@runOnUiThread
                    for (e in calls) {
                        val info = CallTypes.info(e.type)
                        val d = HomeBuilder.duration(e.durationSeconds)
                        val primary = if (!CallTypes.isMissed(e.type) && d.isNotEmpty()) {
                            "Call time " + d
                        } else {
                            info.label + " call"
                        }
                        val secondary = info.arrow + " " + info.label + " · " +
                            HomeBuilder.dayTitle(this, e.dateMillis) + ", " + HomeBuilder.time(this, e.dateMillis)
                        Ui.row(
                            this, activityCard, R.drawable.ic_call, primary, secondary,
                            onClick = { showFullHistory(c, keys) }
                        )
                    }
                    Ui.row(
                        this, activityCard, R.drawable.ic_history, "See all in History", null,
                        onClick = { showFullHistory(c, keys) }
                    )
                    activityCard.visibility = View.VISIBLE
                }
            }.start()
        }

        // ----- WhatsApp expandable section integration -----
        if (c.phones.isNotEmpty()) {
            setupWhatsAppSection(c.phones[0].number)
        }

        // ----- email -----
        if (c.emails.isNotEmpty()) {
            val card = Ui.card(this, content, "Email")
            for ((i, e) in c.emails.withIndex()) {
                Ui.row(
                    this, card, if (i == 0) R.drawable.ic_email else null, e.address, e.type,
                    onClick = { Actions.email(this, e.address) },
                    onLong = {
                        Actions.copy(this, e.address)
                        Actions.toast(this, "Email copied")
                    }
                )
            }
        }

        // ----- chat and social apps -----
        if (c.phones.isNotEmpty()) buildSocialGrid(c)

        // ----- labels -----
        run {
            val card = Ui.card(this, content, "Labels")
            val names = groups.filter { it.id in c.groupIds }.map { it.title }.distinct().sorted()
            Ui.row(
                this, card, R.drawable.ic_label,
                if (names.isEmpty()) "Add to a label" else names.joinToString(", "),
                if (names.isEmpty()) "Group people like Family, Friends or Work" else "Tap to change",
                onClick = { manageLabels(c) }
            )
        }

        // ----- more details -----
        val hasMore = c.department.isNotEmpty() || c.nickname.isNotEmpty() || c.addresses.isNotEmpty() ||
            c.websites.isNotEmpty() || c.events.isNotEmpty() || c.relations.isNotEmpty() ||
            c.notes.isNotEmpty() || (c.company.isNotEmpty() && c.jobTitle.isNotEmpty())
        if (hasMore) {
            val card = Ui.card(this, content, null)
            val box = LinearLayout(this)
            box.orientation = LinearLayout.VERTICAL
            box.visibility = if (moreOpen) View.VISIBLE else View.GONE

            val toggle = Ui.row(this, card, R.drawable.ic_expand, "More details", null)
            val chevron = (toggle as LinearLayout).getChildAt(0)
            chevron.rotation = if (moreOpen) 180f else 0f
            toggle.setOnClickListener {
                moreOpen = !moreOpen
                TransitionManager.beginDelayedTransition(content)
                box.visibility = if (moreOpen) View.VISIBLE else View.GONE
                chevron.animate().rotation(if (moreOpen) 180f else 0f).setDuration(180).start()
            }
            card.addView(box)

            if (c.company.isNotEmpty() || c.jobTitle.isNotEmpty() || c.department.isNotEmpty()) {
                val primary = if (c.company.isNotEmpty()) c.company else c.jobTitle
                val secondary = listOf(c.jobTitle, c.department)
                    .filter { it.isNotEmpty() && it != primary }.joinToString(" - ")
                Ui.row(this, box, R.drawable.ic_business, primary, if (secondary.isEmpty()) "Company" else secondary)
            }
            if (c.nickname.isNotEmpty()) Ui.row(this, box, R.drawable.ic_person, c.nickname, "Nickname")
            for (a in c.addresses) {
                Ui.row(
                    this, box, R.drawable.ic_location, a.value, a.label,
                    onClick = { Actions.directions(this, a.value) }
                )
            }
            for (w in c.websites) {
                Ui.row(this, box, R.drawable.ic_website, w.value, w.label, onClick = { Actions.openUrl(this, w.value) })
            }
            for (ev in c.events) {
                Ui.row(this, box, R.drawable.ic_event, ContactsRepository.prettyDate(ev.value), ev.label)
            }
            for (r in c.relations) Ui.row(this, box, R.drawable.ic_people, r.value, r.label)
            if (c.notes.isNotEmpty()) Ui.row(this, box, R.drawable.ic_notes, c.notes, "Notes")
        }

        // ----- source -----
        val src = Ui.card(this, content, null)
        Ui.row(this, src, R.drawable.ic_cloud, Actions.sourceLabel(c), null)
    }

    private fun hasCallLogAccess(): Boolean =
        ContextCompat.checkSelfPermission(this, Manifest.permission.READ_CALL_LOG) ==
            PackageManager.PERMISSION_GRANTED

    private fun showFullHistory(c: Contact, keys: Set<String>) {
        Thread {
            val all = CallLogRepository.loadForKeys(this, keys, 200)
            runOnUiThread {
                if (isFinishing || isDestroyed) return@runOnUiThread
                CallHistorySheet.show(this, c.name, all)
            }
        }.start()
    }

    private fun setupWhatsAppSection(rawNumber: String) {
        // Re-inflate or build the section dynamically inside content
        val sectionView = LayoutInflater.from(this).inflate(R.layout.activity_detail, content, false)
        val waCard = sectionView.findViewById<LinearLayout>(R.id.whatsappSection)

        if (waCard != null) {
            (waCard.parent as? ViewGroup)?.removeView(waCard)

            val header = waCard.findViewById<LinearLayout>(R.id.whatsappHeader)
            val container = waCard.findViewById<LinearLayout>(R.id.whatsappActionsContainer)
            val icon = waCard.findViewById<ImageView>(R.id.whatsappExpandIcon)

            header?.setOnClickListener {
                isWhatsappExpanded = !isWhatsappExpanded
                TransitionManager.beginDelayedTransition(content)
                container?.visibility = if (isWhatsappExpanded) View.VISIBLE else View.GONE
                icon?.animate()?.rotation(if (isWhatsappExpanded) 180f else 0f)?.setDuration(180)?.start()
            }

            // Pass the original number; openWhatsApp applies country-code normalization.
            waCard.findViewById<Button>(R.id.btnWaMessage)?.setOnClickListener {
                openWhatsApp(rawNumber, "send")
            }
            waCard.findViewById<Button>(R.id.btnWaCall)?.setOnClickListener {
                openWhatsApp(rawNumber, "call")
            }
            waCard.findViewById<Button>(R.id.btnWaVideo)?.setOnClickListener {
                openWhatsApp(rawNumber, "videocall")
            }

            content.addView(waCard)
        }
    }

    /**
     * Opens WhatsApp for the given number.
     *
     * WhatsApp does **not** expose a public deep-link that starts a voice or video call
     * from third-party apps. The old `whatsapp://call?phone=...` URI is rejected with
     * "Invalid call". We therefore:
     *  - Message → open the chat (official wa.me / api.whatsapp.com)
     *  - Call / Video → open the same chat so the user can tap Call / Video inside WhatsApp
     *
     * Numbers are normalized to full international digits (no +) using Settings country code.
     */
    private fun openWhatsApp(number: String, actionType: String) {
        val cleanNumber = Actions.international(this, number)
        if (cleanNumber.isBlank()) {
            Toast.makeText(
                this,
                "This contact does not have a valid phone number.",
                Toast.LENGTH_SHORT
            ).show()
            return
        }

        // Prefer consumer WhatsApp; fall back to WhatsApp Business.
        val pkg = when {
            Actions.isInstalled(this, Social.whatsapp) -> "com.whatsapp"
            packageManager.getLaunchIntentForPackage("com.whatsapp.w4b") != null -> "com.whatsapp.w4b"
            else -> null
        }
        if (pkg == null) {
            Toast.makeText(this, "WhatsApp is not installed.", Toast.LENGTH_SHORT).show()
            try {
                startActivity(Intent(Intent.ACTION_VIEW, Uri.parse("market://details?id=com.whatsapp")))
            } catch (_: Exception) {
                startActivity(
                    Intent(
                        Intent.ACTION_VIEW,
                        Uri.parse("https://play.google.com/store/apps/details?id=com.whatsapp")
                    )
                )
            }
            return
        }

        // Official chat URL — works for message; for call/video it lands in the chat
        // where the user can start the call with one tap inside WhatsApp.
        val chatUri = Uri.parse("https://wa.me/$cleanNumber")

        try {
            val intent = Intent(Intent.ACTION_VIEW, chatUri).apply {
                setPackage(pkg)
                addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            }
            startActivity(intent)
            if (actionType == "call" || actionType == "videocall") {
                val kind = if (actionType == "videocall") "video call" else "call"
                Toast.makeText(
                    this,
                    "Tap the $kind button in WhatsApp",
                    Toast.LENGTH_SHORT
                ).show()
            }
        } catch (e: Exception) {
            // Last resort: open without forcing the package.
            try {
                startActivity(Intent(Intent.ACTION_VIEW, chatUri))
            } catch (_: Exception) {
                Toast.makeText(
                    this,
                    "Could not open WhatsApp for this number.",
                    Toast.LENGTH_SHORT
                ).show()
            }
        }
    }

    private fun buildSocialGrid(c: Contact) {
        val card = Ui.card(this, content, "Chat and social apps")
        val grid = GridLayout(this)
        grid.columnCount = 4
        for (app in Social.apps) {
            val cell = LinearLayout(this)
            cell.orientation = LinearLayout.VERTICAL
            cell.gravity = Gravity.CENTER
            cell.setPadding(0, dp(8), 0, dp(8))
            val icon = ImageView(this)
            icon.setImageResource(app.icon)
            icon.layoutParams = LinearLayout.LayoutParams(dp(44), dp(44))
            icon.contentDescription = app.label
            val label = TextView(this)
            label.text = app.label
            label.textSize = 11f
            label.gravity = Gravity.CENTER
            label.maxLines = 1
            label.setTextColor(Ui.color(this, R.color.app_text_secondary))
            label.setPadding(0, dp(4), 0, 0)
            cell.addView(icon)
            cell.addView(label)
            cell.alpha = if (Actions.isInstalled(this, app)) 1f else 0.35f
            cell.setOnClickListener {
                Actions.withNumber(this, c) { n -> Actions.openSocial(this, app, n) }
            }
            val lp = GridLayout.LayoutParams(
                GridLayout.spec(GridLayout.UNDEFINED),
                GridLayout.spec(GridLayout.UNDEFINED, 1f)
            )
            lp.width = 0
            grid.addView(cell, lp)
        }
        card.addView(grid)
    }

    private fun manageLabels(c: Contact) {
        val titles = groups.map { it.title }.distinct().sorted()
        if (titles.isEmpty()) {
            AlertDialog.Builder(this)
                .setTitle("No labels yet")
                .setMessage("Create a label such as Family, Friends or Work.")
                .setPositiveButton("Create label") { _, _ -> promptNewLabel() }
                .setNegativeButton("Cancel", null)
                .show()
            return
        }
        val checked = BooleanArray(titles.size) { i ->
            groups.any { it.title == titles[i] && it.id in c.groupIds }
        }
        val original = checked.copyOf()
        AlertDialog.Builder(this)
            .setTitle("Labels")
            .setMultiChoiceItems(titles.toTypedArray(), checked) { _, _, _ -> }
            .setPositiveButton("Save") { _, _ ->
                Thread {
                    var ok = true
                    for (i in titles.indices) {
                        if (checked[i] != original[i]) {
                            val gs = groups.filter { it.title == titles[i] }
                            ok = ContactWriter.setMembership(this, c, gs, checked[i]) && ok
                        }
                    }
                    runOnUiThread {
                        if (!ok) Actions.toast(this, "This label is not available for the account storing this contact")
                        load()
                    }
                }.start()
            }
            .setNeutralButton("New label") { _, _ -> promptNewLabel() }
            .setNegativeButton("Cancel", null)
            .show()
    }

    private fun promptNewLabel() {
        val et = EditText(this)
        et.hint = "Label name"
        val box = LinearLayout(this)
        box.setPadding(dp(24), dp(8), dp(24), 0)
        box.addView(et, LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT))
        AlertDialog.Builder(this)
            .setTitle("New label")
            .setView(box)
            .setPositiveButton("Create") { _, _ ->
                val t = et.text.toString().trim()
                if (t.isNotEmpty()) {
                    Thread {
                        val ok = ContactWriter.createGroup(this, t)
                        runOnUiThread {
                            if (!ok) Actions.toast(this, "Could not create label")
                            load()
                        }
                    }.start()
                }
            }
            .setNegativeButton("Cancel", null)
            .show()
    }

    private fun showMore(c: Contact) {
        val acts = ArrayList<Ui.SheetAction>()
        acts.add(Ui.SheetAction("Share contact", R.drawable.ic_share) { Actions.share(this, c) })
        if (c.phones.isNotEmpty()) {
            acts.add(Ui.SheetAction("Copy number", R.drawable.ic_copy) { Actions.copyNumber(this, c) })
        }
        if (c.addresses.isNotEmpty()) {
            acts.add(Ui.SheetAction("Directions", R.drawable.ic_location) {
                Actions.directions(this, c.addresses[0].value)
            })
        }
        acts.add(Ui.SheetAction("Edit in system editor", R.drawable.ic_edit) { Actions.systemEdit(this, c) })
        acts.add(Ui.SheetAction("Delete", R.drawable.ic_delete, true) {
            Actions.confirmDelete(this, c) { finish() }
        })
        Ui.showSheet(this, "More", acts)
    }
}'''

FILES['app/src/main/java/com/example/fastcontacts/Dialpad.kt'] = r'''package com.example.fastcontacts

import android.os.Handler
import android.os.Looper
import android.view.LayoutInflater
import android.view.MotionEvent
import android.view.View
import android.view.ViewGroup
import android.widget.GridLayout
import android.widget.ImageButton
import android.widget.ImageView
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import androidx.recyclerview.widget.DiffUtil
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.ListAdapter
import androidx.recyclerview.widget.RecyclerView
import java.util.concurrent.Executors
import java.util.concurrent.atomic.AtomicInteger

/** Horizontal strip of suggested contacts shown above the keypad. */
class SuggestAdapter(
    private val onClick: (Contact) -> Unit,
    private val onLongClick: (Contact) -> Unit
) : ListAdapter<Contact, SuggestAdapter.VH>(Diff()) {

    private class Diff : DiffUtil.ItemCallback<Contact>() {
        override fun areItemsTheSame(a: Contact, b: Contact): Boolean = a.id == b.id
        override fun areContentsTheSame(a: Contact, b: Contact): Boolean = a == b
    }

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): VH {
        val v = LayoutInflater.from(parent.context).inflate(R.layout.item_suggested, parent, false)
        return VH(v)
    }

    override fun onBindViewHolder(holder: VH, position: Int) {
        val c = getItem(position)
        holder.avatar.bind(c)
        holder.name.text = c.firstName.ifBlank { c.name }
        holder.itemView.contentDescription = c.name
        holder.itemView.setOnClickListener { onClick(c) }
        holder.itemView.setOnLongClickListener {
            onLongClick(c)
            true
        }
    }

    class VH(view: View) : RecyclerView.ViewHolder(view) {
        val avatar: AvatarView = view.findViewById(R.id.sugAvatar)
        val name: TextView = view.findViewById(R.id.sugName)
    }
}

class DialpadController(
    private val activity: AppCompatActivity,
    root: View,
    openContact: (Contact) -> Unit
) {
    private val number = StringBuilder()

    private val display: TextView =
        root.findViewById(R.id.dialDisplay)

    private val suggestSection: View =
        root.findViewById(R.id.suggestSection)

    private val suggestedStrip: RecyclerView =
        root.findViewById(R.id.suggestedStrip)

    private val suggestedEmpty: View =
        root.findViewById(R.id.suggestedEmpty)

    private val matchesTitle: View =
        root.findViewById(R.id.matchesTitle)

    private val keypad: GridLayout =
        root.findViewById(R.id.keypad)

    private val toggleKeypad: ImageView =
        root.findViewById(R.id.btnToggleKeypad)

    private val dialMatches: RecyclerView =
        root.findViewById(R.id.dialMatches)

    private val btnAdd: ImageButton =
        root.findViewById(R.id.btnAddContact)

    @Volatile
    private var contacts: List<Contact> = emptyList()

    @Volatile
    private var engine: SearchEngine = SearchEngine(emptyList())

    private val searchExecutor = Executors.newSingleThreadExecutor()
    private val handler = Handler(Looper.getMainLooper())
    private val searchGeneration = AtomicInteger(0)
    private var pendingSearch: Runnable? = null

    private val adapter = ContactAdapter(
        onClick = openContact,
        onCallClick = { contact ->
            Actions.withNumber(activity, contact) { n ->
                Actions.call(activity, n)
            }
        },
        onSmsClick = { contact ->
            Actions.withNumber(activity, contact) { n ->
                Actions.sms(activity, n)
            }
        }
    )

    private val suggestAdapter = SuggestAdapter(
        onClick = { contact ->
            // Tapping a suggestion fills the number so it can be checked, then called.
            Actions.withNumber(activity, contact) { n ->
                number.setLength(0)
                number.append(n.filter { it.isDigit() || it == '+' || it == '*' || it == '#' })
                refresh()
            }
        },
        onLongClick = openContact
    )

    init {
        dialMatches.layoutManager = LinearLayoutManager(activity)
        dialMatches.adapter = adapter

        suggestedStrip.layoutManager =
            LinearLayoutManager(activity, LinearLayoutManager.HORIZONTAL, false)
        suggestedStrip.adapter = suggestAdapter

        val keys = listOf(
            "1" to "",
            "2" to "ABC",
            "3" to "DEF",
            "4" to "GHI",
            "5" to "JKL",
            "6" to "MNO",
            "7" to "PQRS",
            "8" to "TUV",
            "9" to "WXYZ",
            "*" to "",
            "0" to "+",
            "#" to ""
        )

        for ((digit, letters) in keys) {
            val keyView = LayoutInflater.from(activity)
                .inflate(R.layout.view_dial_key, keypad, false)

            keyView.findViewById<TextView>(R.id.keyDigit).text = digit
            keyView.findViewById<TextView>(R.id.keyLetters).text = letters

            val params = GridLayout.LayoutParams(
                GridLayout.spec(GridLayout.UNDEFINED),
                GridLayout.spec(GridLayout.UNDEFINED, 1f)
            )

            params.width = 0
            params.height = Ui.dp(activity, 58)
            params.setMargins(
                Ui.dp(activity, 5),
                Ui.dp(activity, 4),
                Ui.dp(activity, 5),
                Ui.dp(activity, 4)
            )

            keyView.layoutParams = params
            keyView.contentDescription = digit

            keyView.setOnTouchListener { view, event ->
                when (event.actionMasked) {
                    MotionEvent.ACTION_DOWN -> {
                        view.animate()
                            .scaleX(0.94f)
                            .scaleY(0.94f)
                            .setDuration(70)
                            .start()
                    }

                    MotionEvent.ACTION_UP,
                    MotionEvent.ACTION_CANCEL -> {
                        view.animate()
                            .scaleX(1f)
                            .scaleY(1f)
                            .setDuration(110)
                            .start()
                    }
                }
                false
            }

            keyView.setOnClickListener {
                Ui.tap(keyView)
                number.append(digit)
                refresh()
            }

            if (digit == "0") {
                keyView.setOnLongClickListener {
                    number.append("+")
                    refresh()
                    true
                }
            }

            keypad.addView(keyView)
        }

        toggleKeypad.setOnClickListener {
            val isVisible = keypad.visibility == View.VISIBLE

            keypad.visibility = if (isVisible) {
                View.GONE
            } else {
                View.VISIBLE
            }

            toggleKeypad.rotation = if (isVisible) 180f else 0f

            toggleKeypad.contentDescription = if (isVisible) {
                "Show dialpad"
            } else {
                "Hide dialpad"
            }

            dialMatches.requestLayout()
            suggestSection.requestLayout()
        }

        root.findViewById<View>(R.id.btnDialCall)
            .setOnClickListener {
                if (number.isNotEmpty()) {
                    Actions.call(activity, number.toString())
                }
            }

        btnAdd.setOnClickListener {
            if (number.isNotEmpty()) {
                Actions.create(activity, number.toString())
            } else {
                Actions.toast(activity, "Enter a number first")
            }
        }

        val backspace =
            root.findViewById<ImageButton>(R.id.btnBackspace)

        backspace.setOnClickListener {
            if (number.isNotEmpty()) {
                number.deleteCharAt(number.length - 1)
            }
            refresh()
        }

        backspace.setOnLongClickListener {
            number.setLength(0)
            refresh()
            true
        }

        refresh()
    }

    fun setContacts(list: List<Contact>) {
        contacts = list
        engine = SearchEngine(list)
        refresh()
    }

    fun setSuggestions(list: List<Contact>) {
        suggestAdapter.submitList(list)
        suggestedStrip.visibility = if (list.isEmpty()) View.GONE else View.VISIBLE
        suggestedEmpty.visibility = if (list.isEmpty()) View.VISIBLE else View.GONE
    }

    fun dispose() {
        pendingSearch?.let(handler::removeCallbacks)
        searchExecutor.shutdownNow()
    }

    private fun refresh() {
        val query = number.toString()

        display.text = query
        display.textSize = if (number.length > 14) 24f else 30f
        btnAdd.visibility = if (query.isEmpty()) View.INVISIBLE else View.VISIBLE

        val searching = query.isNotEmpty()

        if (!searching) {
            suggestSection.visibility = View.VISIBLE
            matchesTitle.visibility = View.GONE
            dialMatches.visibility = View.GONE

            pendingSearch?.let(handler::removeCallbacks)
            searchGeneration.incrementAndGet()
            adapter.submit(emptyList())
            return
        }

        // The results area is flexible space above the keypad sheet, so the
        // keypad never jumps when the first digit is typed.
        suggestSection.visibility = View.GONE
        matchesTitle.visibility = View.VISIBLE
        dialMatches.visibility = View.VISIBLE

        pendingSearch?.let(handler::removeCallbacks)

        val task = Runnable {
            val generation = searchGeneration.incrementAndGet()

            searchExecutor.execute {
                // Prefer the pre-indexed engine built in setContacts().
                val matches = engine.search(query).take(20)

                handler.post {
                    if (
                        generation == searchGeneration.get() &&
                        number.toString() == query
                    ) {
                        adapter.submit(matches)
                    }
                }
            }
        }

        pendingSearch = task
        // Short debounce keeps typing responsive without flooding the executor.
        handler.postDelayed(task, 40L)
    }
}
'''

FILES['app/src/main/java/com/example/fastcontacts/MainActivity.kt'] = r'''package com.example.fastcontacts

import android.Manifest
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.provider.CallLog
import android.speech.RecognizerIntent
import android.transition.TransitionManager
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.view.animation.DecelerateInterpolator
import android.view.inputmethod.InputMethodManager
import android.widget.ArrayAdapter
import android.widget.Button
import android.widget.EditText
import android.widget.ImageButton
import android.widget.ImageView
import android.widget.LinearLayout
import android.widget.ListView
import android.widget.PopupMenu
import android.widget.TextView
import androidx.activity.OnBackPressedCallback
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity
import androidx.core.app.ActivityOptionsCompat
import androidx.core.content.ContextCompat
import androidx.core.widget.doAfterTextChanged
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView
import java.util.concurrent.Executors
import com.google.android.material.bottomnavigation.BottomNavigationView
import com.google.android.material.chip.Chip
import com.google.android.material.chip.ChipGroup
import com.google.android.material.floatingactionbutton.FloatingActionButton

class MainActivity : AppCompatActivity() {

    private lateinit var adapter: ContactAdapter
    private lateinit var dialpad: DialpadController
    private lateinit var root: ViewGroup
    private lateinit var header: View
    private lateinit var search: EditText
    private lateinit var btnClear: ImageButton
    private lateinit var chipsScroll: View
    private lateinit var chipGroup: ChipGroup
    private lateinit var list: RecyclerView
    private lateinit var paneHome: View
    private lateinit var paneContacts: View
    private lateinit var paneDialpad: View
    private lateinit var homeChipsScroll: View
    private lateinit var homeChipGroup: ChipGroup
    private lateinit var btnMic: ImageButton
    private lateinit var emptyContacts: View
    private lateinit var emptyPermission: View
    private lateinit var index: AlphabetIndexView
    private lateinit var bubble: TextView
    private lateinit var fab: FloatingActionButton
    private lateinit var nav: BottomNavigationView

    private var all: List<Contact> = emptyList()
    private var sortedAll: List<Contact> = emptyList()
    private var groups: List<ContactGroup> = emptyList()
    private var labelFilter: String? = null
    /** Reused across keystrokes so the search index is built once per contact load. */
    @Volatile
    private var searchEngine: SearchEngine = SearchEngine(emptyList())
    // 0 = Home (recents), 1 = Contacts. The keypad is a slide-up overlay on top of either.
    private var tab = 0
    private var keypadOpen = false
    private var homeFilter = 0
    private val homeChipIds = ArrayList<Int>()
    private var callEntries: List<CallLogEntry> = emptyList()
    private var phoneIndex: PhoneIndex = PhoneIndex(emptyList())
    private val mainHandler = Handler(Looper.getMainLooper())
    private var filterRunnable: Runnable? = null
    private var loadGeneration = 0
    private var filterGeneration = 0
    private val filterExecutor = Executors.newSingleThreadExecutor()
    private lateinit var homeAdapter: HomeAdapter
    private var lastQuery = ""
    private val chipTitles = HashMap<Int, String?>()

    private val permissionLauncher = registerForActivityResult(
        ActivityResultContracts.RequestMultiplePermissions()
    ) {
        if (hasContactsPermission()) loadContacts() else applyFilter()
        if (hasCallLogPermission()) loadCallLog()
    }

    private val organizeLauncher = registerForActivityResult(
        ActivityResultContracts.StartActivityForResult()
    ) { r ->
        val title = r.data?.getStringExtra("label_title")
        if (title != null) {
            labelFilter = title
            nav.selectedItemId = R.id.nav_contacts
        }
    }

    private val voiceLauncher = registerForActivityResult(
        ActivityResultContracts.StartActivityForResult()
    ) { r ->
        val text = r.data?.getStringArrayListExtra(RecognizerIntent.EXTRA_RESULTS)?.firstOrNull()
        if (r.resultCode == RESULT_OK && !text.isNullOrBlank()) {
            search.setText(text)
            search.setSelection(text.length)
        }
    }

    private val backCallback = object : OnBackPressedCallback(false) {
        override fun handleOnBackPressed() {
            nav.selectedItemId = if (tab == 0) R.id.nav_home else R.id.nav_contacts
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)
        Ui.systemBars(this)

        root = findViewById(R.id.root)
        header = findViewById(R.id.header)
        search = findViewById(R.id.search)
        btnClear = findViewById(R.id.btnClearSearch)
        chipsScroll = findViewById(R.id.chipsScroll)
        chipGroup = findViewById(R.id.chipGroup)
        list = findViewById(R.id.list)
        paneHome = findViewById(R.id.paneHome)
        paneContacts = findViewById(R.id.paneContacts)
        paneDialpad = findViewById(R.id.paneDialpad)
        homeChipsScroll = findViewById(R.id.homeChipsScroll)
        homeChipGroup = findViewById(R.id.homeChipGroup)
        btnMic = findViewById(R.id.btnMic)
        emptyContacts = findViewById(R.id.emptyContacts)
        emptyPermission = findViewById(R.id.emptyPermission)
        index = findViewById(R.id.alphabetIndex)
        bubble = findViewById(R.id.letterBubble)
        fab = findViewById(R.id.fab)
        nav = findViewById(R.id.bottomNav)

        adapter = makeAdapter()
        list.layoutManager = LinearLayoutManager(this)
        list.adapter = adapter

        dialpad = DialpadController(this, paneDialpad) { openDetail(it) }
        homeAdapter = HomeAdapter(
            onAvatar = { g -> onHomeAvatar(g) },
            onCall = { g -> Actions.call(this, g.number) },
            onMessage = { g -> Actions.sms(this, g.number) },
            onHistory = { g -> showHistory(g) },
            onFavourite = { c -> openDetail(c) },
            onAddFavourite = { showAddFavourite() },
            onNotice = { if (!hasCallLogPermission()) requestCallLogPermission() }
        )
        findViewById<RecyclerView>(R.id.recentCalls).apply {
            layoutManager = LinearLayoutManager(this@MainActivity)
            adapter = homeAdapter
            isNestedScrollingEnabled = true
        }
        buildHomeChips()
        onBackPressedDispatcher.addCallback(this, backCallback)

        search.doAfterTextChanged {
            btnClear.visibility = if (it.isNullOrEmpty()) View.GONE else View.VISIBLE
            btnMic.visibility = if (it.isNullOrEmpty()) View.VISIBLE else View.GONE
            // Searching from Home shows the matching contacts.
            if (!it.isNullOrEmpty() && tab == 0 && !keypadOpen) nav.selectedItemId = R.id.nav_contacts
            filterRunnable?.let(mainHandler::removeCallbacks)
            val task = Runnable { applyFilter() }
            filterRunnable = task
            mainHandler.postDelayed(task, 50L)
        }
        btnClear.setOnClickListener { search.setText("") }
        btnMic.setOnClickListener {
            try {
                val i = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH)
                i.putExtra(
                    RecognizerIntent.EXTRA_LANGUAGE_MODEL,
                    RecognizerIntent.LANGUAGE_MODEL_FREE_FORM
                )
                i.putExtra(RecognizerIntent.EXTRA_PROMPT, "Search contacts")
                voiceLauncher.launch(i)
            } catch (e: Exception) {
                Actions.toast(this, "Voice search is not available on this device")
            }
        }

        findViewById<ImageButton>(R.id.btnMenu).setOnClickListener { v ->
            val pm = PopupMenu(this, v)
            pm.menu.add("Organize")
            pm.menu.add("Settings")
            pm.setOnMenuItemClickListener { item ->
                if (item.title == "Organize") {
                    organizeLauncher.launch(Intent(this, OrganizeActivity::class.java))
                } else {
                    startActivity(Intent(this, SettingsActivity::class.java))
                }
                true
            }
            pm.show()
        }

        fab.setOnClickListener { Actions.create(this) }

        index.onLetter = { letter -> jumpTo(letter) }
        index.onRelease = { hideBubble() }

        nav.setOnItemSelectedListener { item ->
            when (item.itemId) {
                R.id.nav_home -> {
                    if (!search.text.isNullOrEmpty()) search.setText("")
                    closeKeypad()
                    showTab(0)
                }
                R.id.nav_contacts -> {
                    closeKeypad()
                    showTab(1)
                }
                R.id.nav_keypad -> openKeypad()
            }
            true
        }

        if (!hasContactsPermission()) requestPermissions()
        else if (hasCallLogPermission()) loadCallLog()
        else requestCallLogPermission()
        showTab(0)
        rebuildHome()
    }

    override fun onResume() {
        super.onResume()
        if (hasContactsPermission()) loadContacts() else applyFilter()
        if (hasCallLogPermission()) loadCallLog()
    }

    private fun makeAdapter() = ContactAdapter(
        onClick = { openDetail(it) },
        onCallClick = { c -> Actions.withNumber(this, c) { n -> Actions.call(this, n) } },
        onSmsClick = { c -> Actions.withNumber(this, c) { n -> Actions.sms(this, n) } },
        onLongClick = { showQuickMenu(it) },
        onFavClick = { c ->
            Actions.toggleStar(this, c)
            loadContacts()
        }
    )

    private fun hasContactsPermission(): Boolean =
        ContextCompat.checkSelfPermission(this, Manifest.permission.READ_CONTACTS) ==
            PackageManager.PERMISSION_GRANTED

    private fun requestPermissions() {
        permissionLauncher.launch(
            arrayOf(
                Manifest.permission.READ_CONTACTS,
                Manifest.permission.WRITE_CONTACTS,
                Manifest.permission.CALL_PHONE,
                Manifest.permission.READ_CALL_LOG
            )
        )
    }

    private fun hasCallLogPermission(): Boolean =
        ContextCompat.checkSelfPermission(this, Manifest.permission.READ_CALL_LOG) ==
            PackageManager.PERMISSION_GRANTED

    private fun requestCallLogPermission() {
        permissionLauncher.launch(arrayOf(Manifest.permission.READ_CALL_LOG))
    }

    private fun loadCallLog() {
        if (!hasCallLogPermission()) {
            callEntries = emptyList()
            rebuildHome()
            return
        }
        Thread {
            val entries = CallLogRepository.loadRecent(this, 300)
            runOnUiThread {
                if (isFinishing || isDestroyed) return@runOnUiThread
                callEntries = entries
                rebuildHome()
            }
        }.start()
    }

    private fun buildHomeChips() {
        val inf = LayoutInflater.from(this)
        val titles = listOf("All", "Missed", "Contacts", "Non-contacts")
        for ((i, t) in titles.withIndex()) {
            val chip = inf.inflate(R.layout.chip_filter, homeChipGroup, false) as Chip
            chip.id = View.generateViewId()
            chip.text = t
            chip.isCheckable = true
            homeChipIds.add(chip.id)
            homeChipGroup.addView(chip)
            if (i == 0) chip.isChecked = true
        }
        homeChipGroup.setOnCheckedStateChangeListener { _, ids ->
            homeFilter = if (ids.isEmpty()) 0 else homeChipIds.indexOf(ids[0]).coerceAtLeast(0)
            rebuildHome()
        }
    }

    private fun rebuildHome() {
        val favs = sortedAll.filter { it.starred }
        val allGroups = HomeBuilder.groups(callEntries, phoneIndex)
        var notice: String? = null
        var shown: List<CallGroup> = allGroups
        if (!hasCallLogPermission()) {
            notice = "Tap here to allow call history access"
            shown = emptyList()
        } else {
            shown = when (homeFilter) {
                1 -> allGroups.filter { it.type == CallLog.Calls.MISSED_TYPE }
                2 -> allGroups.filter { it.contact != null }
                3 -> allGroups.filter { it.contact == null }
                else -> allGroups
            }
            if (shown.isEmpty()) {
                notice = if (homeFilter == 0) "No recent calls yet" else "No calls match this filter"
            }
        }
        homeAdapter.submit(HomeBuilder.rows(this, shown, favs, notice))
        dialpad.setSuggestions(buildSuggestions(allGroups, favs))
    }

    private fun buildSuggestions(groups: List<CallGroup>, favs: List<Contact>): List<Contact> {
        val seen = HashSet<Long>()
        val out = ArrayList<Contact>()
        for (g in groups) {
            val c = g.contact ?: continue
            if (seen.add(c.id)) out.add(c)
            if (out.size >= 8) break
        }
        for (c in favs) {
            if (out.size >= 14) break
            if (seen.add(c.id)) out.add(c)
        }
        return out
    }

    private fun onHomeAvatar(g: CallGroup) {
        val c = g.contact
        if (c != null) {
            openDetail(c)
            return
        }
        val acts = ArrayList<Ui.SheetAction>()
        acts.add(Ui.SheetAction("Call", R.drawable.ic_call) { Actions.call(this, g.number) })
        acts.add(Ui.SheetAction("Message", R.drawable.ic_sms) { Actions.sms(this, g.number) })
        acts.add(Ui.SheetAction("Add to contacts", R.drawable.ic_person_add) { Actions.create(this, g.number) })
        acts.add(Ui.SheetAction("Copy number", R.drawable.ic_copy) {
            Actions.copy(this, g.number)
            Actions.toast(this, "Number copied")
        })
        Ui.showSheet(this, g.name, acts)
    }

    private fun showHistory(g: CallGroup) {
        val key = PhoneKey.of(g.number)
        Thread {
            val list = if (hasCallLogPermission()) {
                CallLogRepository.loadForKeys(this, setOf(key), 200)
            } else emptyList()
            runOnUiThread {
                if (isFinishing || isDestroyed) return@runOnUiThread
                CallHistorySheet.show(this, g.name, list)
            }
        }.start()
    }

    private fun showAddFavourite() {
        val candidates = sortedAll.filter { !it.starred }
        if (candidates.isEmpty()) {
            Actions.toast(this, "No contacts to add")
            return
        }
        val engine = SearchEngine(candidates)
        var shown: List<Contact> = candidates.take(100)
        val listAdapter = ArrayAdapter(
            this, android.R.layout.simple_list_item_1, ArrayList(shown.map { it.name })
        )
        val listView = ListView(this)
        listView.adapter = listAdapter
        val input = EditText(this)
        input.hint = "Search contacts"
        input.setSingleLine()
        val box = LinearLayout(this)
        box.orientation = LinearLayout.VERTICAL
        box.setPadding(Ui.dp(this, 20), Ui.dp(this, 8), Ui.dp(this, 20), 0)
        box.addView(
            input,
            LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT)
        )
        box.addView(
            listView,
            LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, Ui.dp(this, 360))
        )
        val dialog = AlertDialog.Builder(this)
            .setTitle("Add favourite")
            .setView(box)
            .setNegativeButton("Cancel", null)
            .create()
        input.doAfterTextChanged { t ->
            shown = engine.search(t?.toString().orEmpty()).take(100)
            listAdapter.clear()
            listAdapter.addAll(shown.map { it.name })
            listAdapter.notifyDataSetChanged()
        }
        listView.setOnItemClickListener { _, _, pos, _ ->
            val c = shown.getOrNull(pos)
            if (c != null) {
                Actions.toggleStar(this, c)
                dialog.dismiss()
                loadContacts()
            }
        }
        dialog.show()
    }

    private fun openDetail(c: Contact) {
        val i = Intent(this, DetailActivity::class.java)
        i.putExtra("contact_id", c.id)
        val opts = ActivityOptionsCompat.makeCustomAnimation(this, R.anim.slide_up_in, R.anim.fade_out_soft)
        startActivity(i, opts.toBundle())
    }

    private fun showTab(t: Int) {
        tab = t
        TransitionManager.beginDelayedTransition(root)
        header.visibility = if (keypadOpen) View.GONE else View.VISIBLE
        updateChipsVisibility()
        if (t == 1 && !keypadOpen) fab.show() else fab.hide()
        swap(paneHome, t == 0)
        swap(paneContacts, t == 1)
        updatePermissionOverlay()
    }

    private fun openKeypad() {
        if (keypadOpen) return
        keypadOpen = true
        backCallback.isEnabled = true
        val imm = getSystemService(Context.INPUT_METHOD_SERVICE) as InputMethodManager
        imm.hideSoftInputFromWindow(search.windowToken, 0)
        search.clearFocus()
        header.visibility = View.GONE
        fab.hide()
        paneDialpad.animate().cancel()
        val h = if (root.height > 0) root.height else Ui.dp(this, 900)
        paneDialpad.translationY = h.toFloat()
        paneDialpad.visibility = View.VISIBLE
        paneDialpad.animate()
            .translationY(0f)
            .setDuration(240L)
            .setInterpolator(DecelerateInterpolator())
            .start()
        updatePermissionOverlay()
    }

    private fun closeKeypad() {
        if (!keypadOpen) return
        keypadOpen = false
        backCallback.isEnabled = false
        header.visibility = View.VISIBLE
        if (tab == 1) fab.show()
        paneDialpad.animate().cancel()
        paneDialpad.animate()
            .translationY(paneDialpad.height.toFloat())
            .setDuration(200L)
            .withEndAction { if (!keypadOpen) paneDialpad.visibility = View.GONE }
            .start()
        updatePermissionOverlay()
    }

    private fun updatePermissionOverlay() {
        emptyPermission.visibility =
            if (!hasContactsPermission() && tab == 1 && !keypadOpen) View.VISIBLE else View.GONE
    }

    private fun swap(pane: View, show: Boolean) {
        if (show) {
            if (pane.visibility != View.VISIBLE) {
                pane.alpha = 0f
                pane.visibility = View.VISIBLE
                pane.animate().alpha(1f).setDuration(160).start()
            }
        } else {
            pane.visibility = View.GONE
        }
    }

    private fun updateChipsVisibility() {
        homeChipsScroll.visibility = if (tab == 0) View.VISIBLE else View.GONE
        chipsScroll.visibility = if (tab == 1 && chipTitles.size > 1) View.VISIBLE else View.GONE
    }

    private fun loadContacts() {
        val generation = ++loadGeneration
        Thread {
            val loaded = ContactsRepository.loadAll(this)
            val g = ContactsRepository.loadGroups(this)
            val sorted = SearchEngine.sorted(loaded, Prefs.sortByLast(this))
            runOnUiThread {
                if (isFinishing || isDestroyed || generation != loadGeneration) return@runOnUiThread
                all = loaded
                groups = g
                sortedAll = sorted
                searchEngine = SearchEngine(sorted)
                phoneIndex = PhoneIndex(sorted)
                rebuildChips()
                applyFilter()
                dialpad.setContacts(sorted)
                rebuildHome()
            }
        }.start()
    }

    private fun rebuildChips() {
        chipGroup.setOnCheckedStateChangeListener(null)
        chipGroup.removeAllViews()
        chipTitles.clear()
        val titles = groups.map { it.title }.distinct().sorted()
        if (labelFilter != null && labelFilter !in titles) labelFilter = null
        val inf = LayoutInflater.from(this)
        fun addChip(text: String, title: String?) {
            val chip = inf.inflate(R.layout.chip_filter, chipGroup, false) as Chip
            chip.id = View.generateViewId()
            chip.text = text
            chip.isCheckable = true
            chipTitles[chip.id] = title
            chipGroup.addView(chip)
            if (title == labelFilter) chip.isChecked = true
        }
        if (titles.isNotEmpty()) {
            addChip("All", null)
            for (t in titles) addChip(t, t)
        }
        chipGroup.setOnCheckedStateChangeListener { _, ids ->
            labelFilter = if (ids.isEmpty()) null else chipTitles[ids[0]]
            applyFilter()
        }
        updateChipsVisibility()
    }

    private fun setEmpty(v: View, icon: Int, title: String, sub: String, btn: String?, run: (() -> Unit)?) {
        v.findViewById<ImageView>(R.id.emptyIcon).setImageResource(icon)
        v.findViewById<TextView>(R.id.emptyTitle).text = title
        v.findViewById<TextView>(R.id.emptySubtitle).text = sub
        val b = v.findViewById<Button>(R.id.emptyButton)
        if (btn != null && run != null) {
            b.text = btn
            b.visibility = View.VISIBLE
            b.setOnClickListener { run() }
        } else {
            b.visibility = View.GONE
        }
    }

    private fun applyFilter() {
        if (!hasContactsPermission()) {
            setEmpty(
                emptyPermission, R.drawable.ic_people, "Contacts access needed",
                "Allow access so Fast Contacts can show and manage your contacts.", "Grant access"
            ) { requestPermissions() }
            updatePermissionOverlay()
            return
        }
        emptyPermission.visibility = View.GONE

        val q = search.text.toString()
        val byLast = Prefs.sortByLast(this)
        val showPhone = Prefs.showPhone(this)
        val showEmail = Prefs.showEmail(this)
        var base = sortedAll
        val lf = labelFilter
        if (lf != null) {
            val ids = groups.filter { it.title == lf }.map { it.id }.toSet()
            base = base.filter { c -> c.groupIds.any { it in ids } }
        }
        val snapshot = base
        val generation = ++filterGeneration
        val useCachedEngine = (lf == null && snapshot === sortedAll)
        filterExecutor.execute {
            val result = if (useCachedEngine) {
                searchEngine.search(q)
            } else {
                SearchEngine(snapshot).search(q)
            }
            runOnUiThread {
                if (isFinishing || isDestroyed || generation != filterGeneration || q != search.text.toString()) {
                    return@runOnUiThread
                }
                val queryChanged = q != lastQuery
                lastQuery = q
                adapter.submit(result, q.isBlank(), byLast, showPhone, showEmail) {
                    if (queryChanged) list.scrollToPosition(0)
                }
                index.visibility = if (
                    tab == 1 && Prefs.alphabetIndex(this) && q.isBlank() && result.isNotEmpty()
                ) View.VISIBLE else View.GONE

                if (result.isEmpty()) {
                    if (all.isEmpty()) {
                        setEmpty(
                            emptyContacts, R.drawable.ic_people, "No contacts yet",
                            "Add your first contact to get started.", "Add contact"
                        ) { Actions.create(this) }
                    } else if (q.isBlank() && labelFilter != null) {
                        setEmpty(
                            emptyContacts, R.drawable.ic_label, "No contacts here yet",
                            "Add people to this label from their contact page.", null, null
                        )
                    } else {
                        setEmpty(
                            emptyContacts, R.drawable.ic_search, "No contacts found",
                            "Try another name or phone number.", null, null
                        )
                    }
                    emptyContacts.visibility = View.VISIBLE
                } else {
                    emptyContacts.visibility = View.GONE
                }
            }
        }
    }

    override fun onDestroy() {
        filterRunnable?.let(mainHandler::removeCallbacks)
        filterExecutor.shutdownNow()
        if (::dialpad.isInitialized) dialpad.dispose()
        super.onDestroy()
    }

    private fun jumpTo(letter: String) {
        val pos = adapter.headerPositions()
        if (pos.isEmpty()) return
        var target = pos[letter]
        if (target == null) {
            val keys = pos.keys.toList()
            val next = keys.firstOrNull { it > letter }
            target = if (next != null) pos[next] else pos[keys.last()]
        }
        (list.layoutManager as LinearLayoutManager).scrollToPositionWithOffset(target ?: 0, 0)
        bubble.text = letter
        bubble.visibility = View.VISIBLE
        bubble.animate().alpha(1f).setDuration(80).start()
    }

    private fun hideBubble() {
        bubble.animate().alpha(0f).setStartDelay(350).setDuration(160).withEndAction {
            bubble.visibility = View.GONE
        }.start()
    }

    // Long-press menu on a contact row.
    private fun showQuickMenu(c: Contact) {
        val acts = ArrayList<Ui.SheetAction>()
        if (c.phones.isNotEmpty()) {
            acts.add(Ui.SheetAction("Call", R.drawable.ic_call) {
                Actions.withNumber(this, c) { n -> Actions.call(this, n) }
            })
            acts.add(Ui.SheetAction("Message", R.drawable.ic_sms) {
                Actions.withNumber(this, c) { n -> Actions.sms(this, n) }
            })
            if (Actions.isInstalled(this, Social.whatsapp)) {
                acts.add(Ui.SheetAction("WhatsApp", R.drawable.ic_whatsapp_placeholder) {
                    Actions.withNumber(this, c) { n -> Actions.openSocial(this, Social.whatsapp, n) }
                })
            }
        }
        acts.add(Ui.SheetAction(
            if (c.starred) "Remove from favorites" else "Add to favorites",
            if (c.starred) R.drawable.ic_star_border else R.drawable.ic_star
        ) {
            Actions.toggleStar(this, c)
            loadContacts()
        })
        acts.add(Ui.SheetAction("Share", R.drawable.ic_share) { Actions.share(this, c) })
        acts.add(Ui.SheetAction("Edit", R.drawable.ic_edit) { Actions.edit(this, c) })
        acts.add(Ui.SheetAction("Delete", R.drawable.ic_delete, true) {
            Actions.confirmDelete(this, c) { loadContacts() }
        })
        Ui.showSheet(this, c.name, acts)
    }
}
'''

FILES['app/src/main/java/com/example/fastcontacts/Ui.kt'] = r'''package com.example.fastcontacts

import android.app.Activity
import android.content.Context
import android.content.res.ColorStateList
import android.content.res.Configuration
import android.graphics.Typeface
import android.graphics.drawable.Drawable
import android.util.TypedValue
import android.view.Gravity
import android.view.HapticFeedbackConstants
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.ImageButton
import android.widget.ImageView
import android.widget.LinearLayout
import android.widget.TextView
import androidx.core.content.ContextCompat
import androidx.core.view.WindowInsetsControllerCompat
import com.google.android.material.bottomsheet.BottomSheetDialog
import com.google.android.material.materialswitch.MaterialSwitch

object Ui {

    fun dp(ctx: Context, v: Int): Int = (v * ctx.resources.displayMetrics.density + 0.5f).toInt()

    fun color(ctx: Context, res: Int): Int = ContextCompat.getColor(ctx, res)

    fun tint(ctx: Context, res: Int): ColorStateList = ColorStateList.valueOf(color(ctx, res))

    fun systemBars(activity: Activity) {
        val night = (activity.resources.configuration.uiMode and Configuration.UI_MODE_NIGHT_MASK) ==
            Configuration.UI_MODE_NIGHT_YES
        val c = WindowInsetsControllerCompat(activity.window, activity.window.decorView)
        c.isAppearanceLightStatusBars = !night
        c.isAppearanceLightNavigationBars = !night
    }

    fun pop(v: View) {
        v.animate().scaleX(1.3f).scaleY(1.3f).setDuration(90).withEndAction {
            v.animate().scaleX(1f).scaleY(1f).setDuration(130).start()
        }.start()
    }

    fun tap(v: View) {
        v.performHapticFeedback(HapticFeedbackConstants.KEYBOARD_TAP)
    }

    private fun selectable(ctx: Context): Drawable? {
        val tv = TypedValue()
        ctx.theme.resolveAttribute(android.R.attr.selectableItemBackground, tv, true)
        return ContextCompat.getDrawable(ctx, tv.resourceId)
    }

    private fun borderless(ctx: Context): Drawable? {
        val tv = TypedValue()
        ctx.theme.resolveAttribute(android.R.attr.selectableItemBackgroundBorderless, tv, true)
        return ContextCompat.getDrawable(ctx, tv.resourceId)
    }

    class SheetAction(val label: String, val icon: Int, val danger: Boolean = false, val run: () -> Unit)

    fun showSheet(ctx: Context, title: String, actions: List<SheetAction>) {
        val dialog = BottomSheetDialog(ctx)
        val root = LinearLayout(ctx)
        root.orientation = LinearLayout.VERTICAL
        root.setPadding(0, dp(ctx, 8), 0, dp(ctx, 16))
        val t = TextView(ctx)
        t.text = title
        t.textSize = 18f
        t.setTypeface(null, Typeface.BOLD)
        t.setTextColor(color(ctx, R.color.app_text))
        t.setPadding(dp(ctx, 24), dp(ctx, 12), dp(ctx, 24), dp(ctx, 8))
        root.addView(t)
        for (a in actions) {
            val v = LayoutInflater.from(ctx).inflate(R.layout.row_sheet_action, root, false)
            val icon = v.findViewById<ImageView>(R.id.sheetIcon)
            val label = v.findViewById<TextView>(R.id.sheetLabel)
            icon.setImageResource(a.icon)
            label.text = a.label
            if (a.danger) {
                icon.imageTintList = tint(ctx, R.color.app_danger)
                label.setTextColor(color(ctx, R.color.app_danger))
            }
            v.setOnClickListener {
                dialog.dismiss()
                a.run()
            }
            root.addView(v)
        }
        dialog.setContentView(root)
        dialog.show()
    }

    // Rounded card section used on the details, organize and settings screens.
    fun card(ctx: Context, parent: LinearLayout, title: String?): LinearLayout {
        val c = LinearLayout(ctx)
        c.orientation = LinearLayout.VERTICAL
        c.background = ContextCompat.getDrawable(ctx, R.drawable.bg_card)
        c.setPadding(dp(ctx, 18), dp(ctx, 14), dp(ctx, 18), dp(ctx, 14))
        val lp = LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT)
        lp.setMargins(dp(ctx, 12), dp(ctx, 5), dp(ctx, 12), dp(ctx, 5))
        parent.addView(c, lp)
        if (title != null) {
            val t = TextView(ctx)
            t.text = title
            t.textSize = 14f
            t.setTypeface(null, Typeface.BOLD)
            t.setTextColor(color(ctx, R.color.app_accent))
            t.setPadding(0, 0, 0, dp(ctx, 4))
            c.addView(t)
        }
        return c
    }

    class Trail(val icon: Int, val desc: String, val tint: Boolean = true, val run: () -> Unit)

    fun row(
        ctx: Context, parent: ViewGroup, icon: Int?, primary: String, secondary: String?,
        onClick: (() -> Unit)? = null, onLong: (() -> Unit)? = null,
        trailing: List<Trail> = emptyList()
    ): View {
        val r = LinearLayout(ctx)
        r.orientation = LinearLayout.HORIZONTAL
        r.gravity = Gravity.CENTER_VERTICAL
        r.minimumHeight = dp(ctx, 56)
        r.setPadding(0, dp(ctx, 6), 0, dp(ctx, 6))

        val iv = ImageView(ctx)
        val ilp = LinearLayout.LayoutParams(dp(ctx, 24), dp(ctx, 24))
        ilp.marginEnd = dp(ctx, 20)
        iv.layoutParams = ilp
        iv.importantForAccessibility = View.IMPORTANT_FOR_ACCESSIBILITY_NO
        if (icon != null) iv.setImageResource(icon) else iv.visibility = View.INVISIBLE
        r.addView(iv)

        val col = LinearLayout(ctx)
        col.orientation = LinearLayout.VERTICAL
        r.addView(col, LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f))

        val p = TextView(ctx)
        p.text = primary
        p.textSize = 16f
        p.setTextColor(color(ctx, R.color.app_text))
        col.addView(p)
        if (secondary != null) {
            val s = TextView(ctx)
            s.text = secondary
            s.textSize = 13f
            s.setTextColor(color(ctx, R.color.app_text_secondary))
            col.addView(s)
        }

        for (t in trailing) {
            val b = ImageButton(ctx)
            b.setImageResource(t.icon)
            b.contentDescription = t.desc
            b.background = borderless(ctx)
            if (!t.tint) b.imageTintList = null
            b.layoutParams = LinearLayout.LayoutParams(dp(ctx, 48), dp(ctx, 48))
            b.setOnClickListener { t.run() }
            r.addView(b)
        }

        if (onClick != null) {
            r.background = selectable(ctx)
            r.setOnClickListener { onClick() }
        }
        if (onLong != null) {
            r.setOnLongClickListener {
                onLong()
                true
            }
        }
        parent.addView(r)
        return r
    }

    fun switchRow(
        ctx: Context, parent: ViewGroup, title: String, subtitle: String?, checked: Boolean,
        onChange: (Boolean) -> Unit
    ): View {
        val r = LinearLayout(ctx)
        r.orientation = LinearLayout.HORIZONTAL
        r.gravity = Gravity.CENTER_VERTICAL
        r.minimumHeight = dp(ctx, 56)
        r.setPadding(0, dp(ctx, 6), 0, dp(ctx, 6))
        val col = LinearLayout(ctx)
        col.orientation = LinearLayout.VERTICAL
        r.addView(col, LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f))
        val p = TextView(ctx)
        p.text = title
        p.textSize = 16f
        p.setTextColor(color(ctx, R.color.app_text))
        col.addView(p)
        if (subtitle != null) {
            val s = TextView(ctx)
            s.text = subtitle
            s.textSize = 13f
            s.setTextColor(color(ctx, R.color.app_text_secondary))
            col.addView(s)
        }
        val sw = MaterialSwitch(ctx)
        sw.isChecked = checked
        sw.setOnCheckedChangeListener { _, v -> onChange(v) }
        r.addView(sw)
        r.setOnClickListener { sw.toggle() }
        parent.addView(r)
        return r
    }
}
'''

FILES['app/src/main/res/drawable/bg_call_pill.xml'] = r'''<?xml version="1.0" encoding="utf-8"?>
<ripple xmlns:android="http://schemas.android.com/apk/res/android"
    android:color="?attr/colorControlHighlight">
    <item>
        <shape android:shape="rectangle">
            <solid android:color="@color/app_call" />
            <corners android:radius="28dp" />
        </shape>
    </item>
</ripple>
'''

FILES['app/src/main/res/drawable/bg_card.xml'] = r'''<?xml version="1.0" encoding="utf-8"?>
<shape xmlns:android="http://schemas.android.com/apk/res/android"
    android:shape="rectangle">
    <solid android:color="@color/app_surface" />
    <corners android:radius="24dp" />
</shape>
'''

FILES['app/src/main/res/drawable/bg_circle.xml'] = r'''<?xml version="1.0" encoding="utf-8"?>
<shape xmlns:android="http://schemas.android.com/apk/res/android"
    android:shape="oval">
    <solid android:color="@color/app_sheet" />
</shape>
'''

FILES['app/src/main/res/drawable/bg_circle_row.xml'] = r'''<?xml version="1.0" encoding="utf-8"?>
<ripple xmlns:android="http://schemas.android.com/apk/res/android"
    android:color="?attr/colorControlHighlight">
    <item>
        <shape android:shape="rectangle">
            <solid android:color="@color/app_surface_variant" />
            <corners android:radius="14dp" />
        </shape>
    </item>
</ripple>
'''

FILES['app/src/main/res/drawable/bg_key.xml'] = r'''<?xml version="1.0" encoding="utf-8"?>
<ripple xmlns:android="http://schemas.android.com/apk/res/android"
    android:color="?attr/colorControlHighlight">
    <item>
        <shape android:shape="rectangle">
            <solid android:color="@color/app_surface" />
            <corners android:radius="29dp" />
        </shape>
    </item>
</ripple>
'''

FILES['app/src/main/res/drawable/bg_pill.xml'] = r'''<?xml version="1.0" encoding="utf-8"?>
<ripple xmlns:android="http://schemas.android.com/apk/res/android"
    android:color="?attr/colorControlHighlight">
    <item>
        <shape android:shape="rectangle">
            <solid android:color="@color/app_accent_container" />
            <corners android:radius="26dp" />
        </shape>
    </item>
</ripple>
'''

FILES['app/src/main/res/drawable/bg_row.xml'] = r'''<?xml version="1.0" encoding="utf-8"?>
<ripple xmlns:android="http://schemas.android.com/apk/res/android"
    android:color="?attr/colorControlHighlight">
    <item>
        <shape android:shape="rectangle">
            <solid android:color="@color/app_surface" />
            <corners android:radius="18dp" />
        </shape>
    </item>
    <item android:id="@android:id/mask">
        <shape android:shape="rectangle">
            <solid android:color="#FFFFFFFF" />
            <corners android:radius="18dp" />
        </shape>
    </item>
</ripple>
'''

FILES['app/src/main/res/drawable/bg_search.xml'] = r'''<?xml version="1.0" encoding="utf-8"?>
<shape xmlns:android="http://schemas.android.com/apk/res/android"
    android:shape="rectangle">
    <solid android:color="@color/app_surface" />
    <corners android:radius="30dp" />
</shape>
'''

FILES['app/src/main/res/drawable/bg_sheet.xml'] = r'''<?xml version="1.0" encoding="utf-8"?>
<shape xmlns:android="http://schemas.android.com/apk/res/android"
    android:shape="rectangle">
    <solid android:color="@color/app_sheet" />
    <corners
        android:topLeftRadius="32dp"
        android:topRightRadius="32dp" />
</shape>
'''

FILES['app/src/main/res/drawable/ic_history.xml'] = r'''<?xml version="1.0" encoding="utf-8"?>
<vector xmlns:android="http://schemas.android.com/apk/res/android"
    android:width="24dp"
    android:height="24dp"
    android:tint="?attr/colorOnSurfaceVariant"
    android:viewportWidth="24"
    android:viewportHeight="24">
    <path
        android:fillColor="#FF000000"
        android:pathData="M13,3c-4.97,0 -9,4.03 -9,9L1,12l3.89,3.89 0.07,0.14L9,12L6,12c0,-3.87 3.13,-7 7,-7s7,3.13 7,7 -3.13,7 -7,7c-1.93,0 -3.68,-0.79 -4.94,-2.06l-1.42,1.42C8.27,19.99 10.51,21 13,21c4.97,0 9,-4.03 9,-9s-4.03,-9 -9,-9zM12,8v5l4.28,2.54 0.72,-1.21 -3.5,-2.08L13.5,8L12,8z" />
</vector>
'''

FILES['app/src/main/res/drawable/ic_home.xml'] = r'''<?xml version="1.0" encoding="utf-8"?>
<vector xmlns:android="http://schemas.android.com/apk/res/android"
    android:width="24dp"
    android:height="24dp"
    android:tint="?attr/colorOnSurfaceVariant"
    android:viewportWidth="24"
    android:viewportHeight="24">
    <path
        android:fillColor="#FF000000"
        android:pathData="M10,20v-6h4v6h5v-8h3L12,3 2,12h3v8z" />
</vector>
'''

FILES['app/src/main/res/drawable/ic_menu.xml'] = r'''<?xml version="1.0" encoding="utf-8"?>
<vector xmlns:android="http://schemas.android.com/apk/res/android"
    android:width="24dp"
    android:height="24dp"
    android:tint="?attr/colorOnSurfaceVariant"
    android:viewportWidth="24"
    android:viewportHeight="24">
    <path
        android:fillColor="#FF000000"
        android:pathData="M3,18h18v-2H3v2zM3,13h18v-2H3v2zM3,6v2h18V6H3z" />
</vector>
'''

FILES['app/src/main/res/drawable/ic_mic.xml'] = r'''<?xml version="1.0" encoding="utf-8"?>
<vector xmlns:android="http://schemas.android.com/apk/res/android"
    android:width="24dp"
    android:height="24dp"
    android:tint="?attr/colorOnSurfaceVariant"
    android:viewportWidth="24"
    android:viewportHeight="24">
    <path
        android:fillColor="#FF000000"
        android:pathData="M12,14c1.66,0 2.99,-1.34 2.99,-3L15,5c0,-1.66 -1.34,-3 -3,-3S9,3.34 9,5v6c0,1.66 1.34,3 3,3zM17.3,11c0,3 -2.54,5.1 -5.3,5.1S6.7,14 6.7,11H5c0,3.41 2.72,6.23 6,6.72V21h2v-3.28c3.28,-0.48 6,-3.3 6,-6.72h-1.7z" />
</vector>
'''

FILES['app/src/main/res/drawable/ic_person_add.xml'] = r'''<?xml version="1.0" encoding="utf-8"?>
<vector xmlns:android="http://schemas.android.com/apk/res/android"
    android:width="24dp"
    android:height="24dp"
    android:tint="?attr/colorOnSurfaceVariant"
    android:viewportWidth="24"
    android:viewportHeight="24">
    <path
        android:fillColor="#FF000000"
        android:pathData="M15,12c2.21,0 4,-1.79 4,-4s-1.79,-4 -4,-4 -4,1.79 -4,4 1.79,4 4,4zM6,10L6,7L4,7v3L1,10v2h3v3h2v-3h3v-2L6,10zM15,14c-2.67,0 -8,1.34 -8,4v2h16v-2c0,-2.66 -5.33,-4 -8,-4z" />
</vector>
'''

FILES['app/src/main/res/layout/activity_main.xml'] = r'''<?xml version="1.0" encoding="utf-8"?>
<LinearLayout xmlns:android="http://schemas.android.com/apk/res/android"
    xmlns:app="http://schemas.android.com/apk/res-auto"
    android:id="@+id/root"
    android:layout_width="match_parent"
    android:layout_height="match_parent"
    android:background="@color/app_bg"
    android:fitsSystemWindows="true"
    android:orientation="vertical">

    <LinearLayout
        android:id="@+id/header"
        android:layout_width="match_parent"
        android:layout_height="wrap_content"
        android:clipChildren="false"
        android:clipToPadding="false"
        android:orientation="vertical">

        <LinearLayout
            android:layout_width="match_parent"
            android:layout_height="56dp"
            android:layout_marginStart="12dp"
            android:layout_marginTop="10dp"
            android:layout_marginEnd="12dp"
            android:layout_marginBottom="8dp"
            android:background="@drawable/bg_search"
            android:elevation="3dp"
            android:gravity="center_vertical"
            android:orientation="horizontal"
            android:paddingStart="4dp"
            android:paddingEnd="4dp">

            <ImageButton
                android:id="@+id/btnMenu"
                android:layout_width="48dp"
                android:layout_height="48dp"
                android:background="?attr/selectableItemBackgroundBorderless"
                android:contentDescription="Menu"
                android:src="@drawable/ic_menu" />

            <EditText
                android:id="@+id/search"
                android:layout_width="0dp"
                android:layout_height="match_parent"
                android:layout_weight="1"
                android:background="@null"
                android:hint="Search contacts"
                android:importantForAutofill="no"
                android:inputType="text"
                android:maxLines="1"
                android:paddingStart="8dp"
                android:paddingEnd="8dp"
                android:textColor="@color/app_text"
                android:textColorHint="@color/app_text_secondary"
                android:textSize="16sp" />

            <ImageButton
                android:id="@+id/btnClearSearch"
                android:layout_width="48dp"
                android:layout_height="48dp"
                android:background="?attr/selectableItemBackgroundBorderless"
                android:contentDescription="Clear search"
                android:src="@drawable/ic_close"
                android:visibility="gone" />

            <ImageButton
                android:id="@+id/btnMic"
                android:layout_width="48dp"
                android:layout_height="48dp"
                android:background="?attr/selectableItemBackgroundBorderless"
                android:contentDescription="Voice search"
                android:src="@drawable/ic_mic" />
        </LinearLayout>

        <HorizontalScrollView
            android:id="@+id/homeChipsScroll"
            android:layout_width="match_parent"
            android:layout_height="wrap_content"
            android:scrollbars="none">

            <com.google.android.material.chip.ChipGroup
                android:id="@+id/homeChipGroup"
                android:layout_width="wrap_content"
                android:layout_height="wrap_content"
                android:paddingStart="12dp"
                android:paddingEnd="12dp"
                android:paddingBottom="4dp"
                app:selectionRequired="true"
                app:singleLine="true"
                app:singleSelection="true" />
        </HorizontalScrollView>

        <HorizontalScrollView
            android:id="@+id/chipsScroll"
            android:layout_width="match_parent"
            android:layout_height="wrap_content"
            android:scrollbars="none"
            android:visibility="gone">

            <com.google.android.material.chip.ChipGroup
                android:id="@+id/chipGroup"
                android:layout_width="wrap_content"
                android:layout_height="wrap_content"
                android:paddingStart="12dp"
                android:paddingEnd="12dp"
                android:paddingBottom="4dp"
                app:selectionRequired="true"
                app:singleLine="true"
                app:singleSelection="true" />
        </HorizontalScrollView>
    </LinearLayout>

    <FrameLayout
        android:layout_width="match_parent"
        android:layout_height="0dp"
        android:layout_weight="1">

        <FrameLayout
            android:id="@+id/paneHome"
            android:layout_width="match_parent"
            android:layout_height="match_parent">

            <androidx.recyclerview.widget.RecyclerView
                android:id="@+id/recentCalls"
                android:layout_width="match_parent"
                android:layout_height="match_parent"
                android:clipToPadding="false"
                android:paddingBottom="24dp" />
        </FrameLayout>

        <FrameLayout
            android:id="@+id/paneContacts"
            android:layout_width="match_parent"
            android:layout_height="match_parent">

            <androidx.recyclerview.widget.RecyclerView
                android:id="@+id/list"
                android:layout_width="match_parent"
                android:layout_height="match_parent"
                android:clipToPadding="false"
                android:paddingEnd="22dp"
                android:paddingBottom="96dp" />

            <com.example.fastcontacts.AlphabetIndexView
                android:id="@+id/alphabetIndex"
                android:layout_width="26dp"
                android:layout_height="match_parent"
                android:layout_gravity="end"
                android:layout_marginTop="8dp"
                android:layout_marginBottom="88dp"
                android:contentDescription="Alphabet index" />

            <include
                android:id="@+id/emptyContacts"
                layout="@layout/view_empty"
                android:layout_width="match_parent"
                android:layout_height="match_parent"
                android:visibility="gone" />
        </FrameLayout>

        <include
            android:id="@+id/paneDialpad"
            layout="@layout/pane_dialpad"
            android:layout_width="match_parent"
            android:layout_height="match_parent"
            android:visibility="gone" />

        <include
            android:id="@+id/emptyPermission"
            layout="@layout/view_empty"
            android:layout_width="match_parent"
            android:layout_height="match_parent"
            android:background="@color/app_bg"
            android:visibility="gone" />

        <com.google.android.material.floatingactionbutton.FloatingActionButton
            android:id="@+id/fab"
            android:layout_width="wrap_content"
            android:layout_height="wrap_content"
            android:layout_gravity="bottom|end"
            android:layout_margin="16dp"
            android:contentDescription="Create contact"
            android:src="@drawable/ic_add" />

        <TextView
            android:id="@+id/letterBubble"
            android:layout_width="72dp"
            android:layout_height="72dp"
            android:layout_gravity="center"
            android:alpha="0"
            android:background="@drawable/bg_bubble"
            android:gravity="center"
            android:textColor="@color/app_on_accent"
            android:textSize="34sp"
            android:textStyle="bold"
            android:visibility="gone" />
    </FrameLayout>

    <com.google.android.material.bottomnavigation.BottomNavigationView
        android:id="@+id/bottomNav"
        android:layout_width="match_parent"
        android:layout_height="wrap_content"
        app:backgroundTint="@color/app_nav_bg"
        app:labelVisibilityMode="labeled"
        app:menu="@menu/bottom_nav" />
</LinearLayout>
'''

FILES['app/src/main/res/layout/chip_filter.xml'] = r'''<?xml version="1.0" encoding="utf-8"?>
<com.google.android.material.chip.Chip xmlns:android="http://schemas.android.com/apk/res/android"
    xmlns:app="http://schemas.android.com/apk/res-auto"
    style="@style/Widget.Material3.Chip.Filter"
    android:layout_width="wrap_content"
    android:layout_height="wrap_content"
    app:checkedIconVisible="false" />
'''

FILES['app/src/main/res/layout/item_call_day.xml'] = r'''<?xml version="1.0" encoding="utf-8"?>
<TextView xmlns:android="http://schemas.android.com/apk/res/android"
    android:id="@+id/dayText"
    android:layout_width="match_parent"
    android:layout_height="wrap_content"
    android:paddingStart="24dp"
    android:paddingTop="14dp"
    android:paddingEnd="16dp"
    android:paddingBottom="6dp"
    android:textColor="@color/app_accent"
    android:textSize="14sp"
    android:textStyle="bold" />
'''

FILES['app/src/main/res/layout/item_call_log.xml'] = r'''<?xml version="1.0" encoding="utf-8"?>
<LinearLayout xmlns:android="http://schemas.android.com/apk/res/android"
    android:layout_width="match_parent"
    android:layout_height="wrap_content"
    android:layout_marginStart="12dp"
    android:layout_marginTop="1dp"
    android:layout_marginEnd="12dp"
    android:layout_marginBottom="1dp"
    android:background="@drawable/bg_row"
    android:orientation="vertical">

    <LinearLayout
        android:id="@+id/callRow"
        android:layout_width="match_parent"
        android:layout_height="wrap_content"
        android:clickable="true"
        android:focusable="true"
        android:gravity="center_vertical"
        android:minHeight="68dp"
        android:orientation="horizontal"
        android:paddingStart="12dp"
        android:paddingTop="8dp"
        android:paddingEnd="4dp"
        android:paddingBottom="8dp">

        <com.example.fastcontacts.AvatarView
            android:id="@+id/callAvatar"
            android:layout_width="48dp"
            android:layout_height="48dp" />

        <LinearLayout
            android:layout_width="0dp"
            android:layout_height="wrap_content"
            android:layout_marginStart="14dp"
            android:layout_weight="1"
            android:orientation="vertical">

            <TextView
                android:id="@+id/callName"
                android:layout_width="match_parent"
                android:layout_height="wrap_content"
                android:ellipsize="end"
                android:maxLines="1"
                android:textColor="@color/app_text"
                android:textSize="16sp" />

            <LinearLayout
                android:layout_width="match_parent"
                android:layout_height="wrap_content"
                android:gravity="center_vertical"
                android:orientation="horizontal">

                <TextView
                    android:id="@+id/callTypeIcon"
                    android:layout_width="wrap_content"
                    android:layout_height="wrap_content"
                    android:paddingEnd="4dp"
                    android:textSize="12sp" />

                <TextView
                    android:id="@+id/callMeta"
                    android:layout_width="0dp"
                    android:layout_height="wrap_content"
                    android:layout_weight="1"
                    android:ellipsize="end"
                    android:maxLines="1"
                    android:textColor="@color/app_text_secondary"
                    android:textSize="13sp" />
            </LinearLayout>

            <TextView
                android:id="@+id/callNumber"
                android:layout_width="match_parent"
                android:layout_height="wrap_content"
                android:ellipsize="end"
                android:maxLines="1"
                android:textColor="@color/app_tertiary"
                android:textSize="13sp"
                android:visibility="gone" />
        </LinearLayout>

        <ImageButton
            android:id="@+id/callBtn"
            android:layout_width="48dp"
            android:layout_height="48dp"
            android:background="?attr/selectableItemBackgroundBorderless"
            android:contentDescription="Call"
            android:src="@drawable/ic_call" />
    </LinearLayout>

    <LinearLayout
        android:id="@+id/callExpanded"
        android:layout_width="match_parent"
        android:layout_height="wrap_content"
        android:orientation="vertical"
        android:paddingStart="12dp"
        android:paddingEnd="12dp"
        android:paddingBottom="10dp"
        android:visibility="gone">

        <LinearLayout
            android:id="@+id/callTimes"
            android:layout_width="match_parent"
            android:layout_height="wrap_content"
            android:orientation="vertical"
            android:paddingStart="62dp" />

        <TextView
            android:id="@+id/callSeeMore"
            android:layout_width="match_parent"
            android:layout_height="wrap_content"
            android:background="?attr/selectableItemBackground"
            android:paddingStart="62dp"
            android:paddingTop="8dp"
            android:paddingBottom="8dp"
            android:text="See more in History"
            android:textColor="@color/app_text_secondary"
            android:textSize="13sp" />

        <LinearLayout
            android:id="@+id/callMessage"
            android:layout_width="match_parent"
            android:layout_height="48dp"
            android:background="@drawable/bg_circle_row"
            android:clickable="true"
            android:focusable="true"
            android:gravity="center_vertical"
            android:orientation="horizontal"
            android:paddingStart="16dp"
            android:paddingEnd="16dp">

            <ImageView
                android:layout_width="22dp"
                android:layout_height="22dp"
                android:importantForAccessibility="no"
                android:src="@drawable/ic_sms" />

            <TextView
                android:layout_width="wrap_content"
                android:layout_height="wrap_content"
                android:layout_marginStart="16dp"
                android:text="Message"
                android:textColor="@color/app_text"
                android:textSize="15sp" />
        </LinearLayout>

        <LinearLayout
            android:id="@+id/callHistory"
            android:layout_width="match_parent"
            android:layout_height="48dp"
            android:layout_marginTop="2dp"
            android:background="@drawable/bg_circle_row"
            android:clickable="true"
            android:focusable="true"
            android:gravity="center_vertical"
            android:orientation="horizontal"
            android:paddingStart="16dp"
            android:paddingEnd="16dp">

            <ImageView
                android:layout_width="22dp"
                android:layout_height="22dp"
                android:importantForAccessibility="no"
                android:src="@drawable/ic_history" />

            <TextView
                android:layout_width="wrap_content"
                android:layout_height="wrap_content"
                android:layout_marginStart="16dp"
                android:text="History"
                android:textColor="@color/app_text"
                android:textSize="15sp" />
        </LinearLayout>
    </LinearLayout>
</LinearLayout>
'''

FILES['app/src/main/res/layout/item_contact.xml'] = r'''<?xml version="1.0" encoding="utf-8"?>
<LinearLayout xmlns:android="http://schemas.android.com/apk/res/android"
    android:layout_width="match_parent"
    android:layout_height="wrap_content"
    android:layout_marginStart="12dp"
    android:layout_marginTop="1dp"
    android:layout_marginEnd="4dp"
    android:layout_marginBottom="1dp"
    android:background="@drawable/bg_row"
    android:gravity="center_vertical"
    android:minHeight="64dp"
    android:orientation="horizontal"
    android:paddingStart="16dp"
    android:paddingTop="8dp"
    android:paddingEnd="4dp"
    android:paddingBottom="8dp">

    <com.example.fastcontacts.AvatarView
        android:id="@+id/avatar"
        android:layout_width="44dp"
        android:layout_height="44dp" />

    <LinearLayout
        android:layout_width="0dp"
        android:layout_height="wrap_content"
        android:layout_marginStart="16dp"
        android:layout_weight="1"
        android:orientation="vertical">

        <TextView
            android:id="@+id/name"
            android:layout_width="match_parent"
            android:layout_height="wrap_content"
            android:ellipsize="end"
            android:maxLines="1"
            android:textColor="@color/app_text"
            android:textSize="16sp" />

        <TextView
            android:id="@+id/number"
            android:layout_width="match_parent"
            android:layout_height="wrap_content"
            android:ellipsize="end"
            android:maxLines="1"
            android:textColor="@color/app_text_secondary"
            android:textSize="14sp" />

        <TextView
            android:id="@+id/email"
            android:layout_width="match_parent"
            android:layout_height="wrap_content"
            android:ellipsize="end"
            android:maxLines="1"
            android:textColor="@color/app_text_secondary"
            android:textSize="12sp"
            android:visibility="gone" />
    </LinearLayout>

    <ImageButton
        android:id="@+id/starBadge"
        android:layout_width="40dp"
        android:layout_height="48dp"
        android:background="?attr/selectableItemBackgroundBorderless"
        android:contentDescription="Remove from favorites"
        android:padding="10dp"
        android:src="@drawable/ic_star"
        android:visibility="gone" />

    <ImageButton
        android:id="@+id/btnSms"
        android:layout_width="48dp"
        android:layout_height="48dp"
        android:background="?attr/selectableItemBackgroundBorderless"
        android:contentDescription="Message"
        android:src="@drawable/ic_sms" />

    <ImageButton
        android:id="@+id/btnCall"
        android:layout_width="48dp"
        android:layout_height="48dp"
        android:background="?attr/selectableItemBackgroundBorderless"
        android:contentDescription="Call"
        android:src="@drawable/ic_call" />
</LinearLayout>
'''

FILES['app/src/main/res/layout/item_favourite.xml'] = r'''<?xml version="1.0" encoding="utf-8"?>
<LinearLayout xmlns:android="http://schemas.android.com/apk/res/android"
    android:layout_width="72dp"
    android:layout_height="wrap_content"
    android:background="?attr/selectableItemBackground"
    android:clickable="true"
    android:focusable="true"
    android:gravity="center_horizontal"
    android:orientation="vertical"
    android:paddingTop="4dp"
    android:paddingBottom="6dp">

    <FrameLayout
        android:layout_width="52dp"
        android:layout_height="52dp">

        <com.example.fastcontacts.AvatarView
            android:id="@+id/favAvatar"
            android:layout_width="match_parent"
            android:layout_height="match_parent" />

        <ImageView
            android:id="@+id/favAddIcon"
            android:layout_width="match_parent"
            android:layout_height="match_parent"
            android:background="@drawable/bg_circle"
            android:importantForAccessibility="no"
            android:padding="14dp"
            android:src="@drawable/ic_person_add"
            android:visibility="gone" />
    </FrameLayout>

    <TextView
        android:id="@+id/favName"
        android:layout_width="match_parent"
        android:layout_height="wrap_content"
        android:layout_marginTop="4dp"
        android:ellipsize="end"
        android:gravity="center"
        android:maxLines="1"
        android:paddingStart="2dp"
        android:paddingEnd="2dp"
        android:textColor="@color/app_text"
        android:textSize="12sp" />
</LinearLayout>
'''

FILES['app/src/main/res/layout/item_home_favourites.xml'] = r'''<?xml version="1.0" encoding="utf-8"?>
<LinearLayout xmlns:android="http://schemas.android.com/apk/res/android"
    android:layout_width="match_parent"
    android:layout_height="wrap_content"
    android:orientation="vertical">

    <LinearLayout
        android:id="@+id/favHeader"
        android:layout_width="wrap_content"
        android:layout_height="wrap_content"
        android:background="?attr/selectableItemBackground"
        android:clickable="true"
        android:focusable="true"
        android:gravity="center_vertical"
        android:orientation="horizontal"
        android:paddingStart="24dp"
        android:paddingTop="10dp"
        android:paddingEnd="16dp"
        android:paddingBottom="6dp">

        <TextView
            android:layout_width="wrap_content"
            android:layout_height="wrap_content"
            android:text="Favourites"
            android:textColor="@color/app_accent"
            android:textSize="14sp"
            android:textStyle="bold" />

        <ImageView
            android:id="@+id/favChevron"
            android:layout_width="18dp"
            android:layout_height="18dp"
            android:layout_marginStart="2dp"
            android:importantForAccessibility="no"
            android:src="@drawable/ic_expand"
            android:tint="@color/app_accent" />
    </LinearLayout>

    <HorizontalScrollView
        android:id="@+id/favScroll"
        android:layout_width="match_parent"
        android:layout_height="wrap_content"
        android:scrollbars="none">

        <LinearLayout
            android:id="@+id/favRow"
            android:layout_width="wrap_content"
            android:layout_height="wrap_content"
            android:orientation="horizontal"
            android:paddingStart="16dp"
            android:paddingEnd="16dp" />
    </HorizontalScrollView>
</LinearLayout>
'''

FILES['app/src/main/res/layout/item_notice.xml'] = r'''<?xml version="1.0" encoding="utf-8"?>
<TextView xmlns:android="http://schemas.android.com/apk/res/android"
    android:id="@+id/noticeText"
    android:layout_width="match_parent"
    android:layout_height="wrap_content"
    android:gravity="center"
    android:padding="32dp"
    android:textColor="@color/app_text_secondary"
    android:textSize="14sp" />
'''

FILES['app/src/main/res/layout/item_suggested.xml'] = r'''<?xml version="1.0" encoding="utf-8"?>
<LinearLayout xmlns:android="http://schemas.android.com/apk/res/android"
    android:layout_width="76dp"
    android:layout_height="wrap_content"
    android:background="?attr/selectableItemBackground"
    android:clickable="true"
    android:focusable="true"
    android:gravity="center_horizontal"
    android:orientation="vertical"
    android:paddingTop="6dp"
    android:paddingBottom="6dp">

    <com.example.fastcontacts.AvatarView
        android:id="@+id/sugAvatar"
        android:layout_width="56dp"
        android:layout_height="56dp" />

    <TextView
        android:id="@+id/sugName"
        android:layout_width="match_parent"
        android:layout_height="wrap_content"
        android:layout_marginTop="4dp"
        android:ellipsize="end"
        android:gravity="center"
        android:maxLines="1"
        android:paddingStart="2dp"
        android:paddingEnd="2dp"
        android:textColor="@color/app_text"
        android:textSize="12sp" />
</LinearLayout>
'''

FILES['app/src/main/res/layout/pane_dialpad.xml'] = r'''<?xml version="1.0" encoding="utf-8"?>
<LinearLayout xmlns:android="http://schemas.android.com/apk/res/android"
    android:layout_width="match_parent"
    android:layout_height="match_parent"
    android:background="@color/app_bg"
    android:clickable="true"
    android:focusable="true"
    android:orientation="vertical">

    <LinearLayout
        android:id="@+id/suggestSection"
        android:layout_width="match_parent"
        android:layout_height="0dp"
        android:layout_weight="1"
        android:orientation="vertical">

        <TextView
            android:layout_width="match_parent"
            android:layout_height="wrap_content"
            android:paddingStart="24dp"
            android:paddingTop="16dp"
            android:paddingBottom="6dp"
            android:text="Suggested"
            android:textColor="@color/app_accent"
            android:textSize="14sp"
            android:textStyle="bold" />

        <androidx.recyclerview.widget.RecyclerView
            android:id="@+id/suggestedStrip"
            android:layout_width="match_parent"
            android:layout_height="wrap_content"
            android:clipToPadding="false"
            android:paddingStart="12dp"
            android:paddingEnd="12dp" />

        <TextView
            android:id="@+id/suggestedEmpty"
            android:layout_width="match_parent"
            android:layout_height="wrap_content"
            android:padding="24dp"
            android:text="Favourite and recently called contacts appear here."
            android:textColor="@color/app_text_secondary"
            android:textSize="14sp"
            android:visibility="gone" />
    </LinearLayout>

    <TextView
        android:id="@+id/matchesTitle"
        android:layout_width="match_parent"
        android:layout_height="wrap_content"
        android:paddingStart="24dp"
        android:paddingTop="16dp"
        android:paddingBottom="6dp"
        android:text="Matching contacts"
        android:textColor="@color/app_accent"
        android:textSize="14sp"
        android:textStyle="bold"
        android:visibility="gone" />

    <androidx.recyclerview.widget.RecyclerView
        android:id="@+id/dialMatches"
        android:layout_width="match_parent"
        android:layout_height="0dp"
        android:layout_weight="1"
        android:clipToPadding="false"
        android:paddingStart="4dp"
        android:paddingEnd="4dp"
        android:visibility="gone" />

    <LinearLayout
        android:id="@+id/dialSheet"
        android:layout_width="match_parent"
        android:layout_height="wrap_content"
        android:background="@drawable/bg_sheet"
        android:orientation="vertical"
        android:paddingBottom="14dp">

        <ImageView
            android:id="@+id/btnToggleKeypad"
            android:layout_width="match_parent"
            android:layout_height="28dp"
            android:background="?attr/selectableItemBackground"
            android:clickable="true"
            android:contentDescription="Hide dialpad"
            android:focusable="true"
            android:paddingTop="4dp"
            android:src="@drawable/ic_expand" />

        <LinearLayout
            android:layout_width="match_parent"
            android:layout_height="wrap_content"
            android:gravity="center_vertical"
            android:orientation="horizontal"
            android:paddingStart="12dp"
            android:paddingEnd="12dp">

            <ImageButton
                android:id="@+id/btnAddContact"
                android:layout_width="48dp"
                android:layout_height="48dp"
                android:background="?attr/selectableItemBackgroundBorderless"
                android:contentDescription="Add to contacts"
                android:src="@drawable/ic_person_add" />

            <TextView
                android:id="@+id/dialDisplay"
                android:layout_width="0dp"
                android:layout_height="wrap_content"
                android:layout_weight="1"
                android:ellipsize="start"
                android:gravity="center"
                android:minHeight="48dp"
                android:singleLine="true"
                android:textColor="@color/app_text"
                android:textSize="30sp" />

            <ImageButton
                android:id="@+id/btnBackspace"
                android:layout_width="48dp"
                android:layout_height="48dp"
                android:background="?attr/selectableItemBackgroundBorderless"
                android:contentDescription="Backspace"
                android:src="@drawable/ic_backspace" />
        </LinearLayout>

        <GridLayout
            android:id="@+id/keypad"
            android:layout_width="match_parent"
            android:layout_height="wrap_content"
            android:columnCount="3"
            android:paddingStart="14dp"
            android:paddingEnd="14dp" />

        <LinearLayout
            android:layout_width="match_parent"
            android:layout_height="wrap_content"
            android:gravity="center"
            android:orientation="horizontal"
            android:paddingTop="8dp">

            <LinearLayout
                android:id="@+id/btnDialCall"
                android:layout_width="wrap_content"
                android:layout_height="56dp"
                android:background="@drawable/bg_call_pill"
                android:clickable="true"
                android:contentDescription="Call"
                android:focusable="true"
                android:gravity="center"
                android:minWidth="132dp"
                android:orientation="horizontal"
                android:paddingStart="24dp"
                android:paddingEnd="24dp">

                <ImageView
                    android:layout_width="22dp"
                    android:layout_height="22dp"
                    android:importantForAccessibility="no"
                    android:src="@drawable/ic_call"
                    android:tint="@color/app_on_call" />

                <TextView
                    android:layout_width="wrap_content"
                    android:layout_height="wrap_content"
                    android:layout_marginStart="10dp"
                    android:text="Call"
                    android:textColor="@color/app_on_call"
                    android:textSize="17sp" />
            </LinearLayout>
        </LinearLayout>
    </LinearLayout>
</LinearLayout>
'''

FILES['app/src/main/res/layout/view_action_pill.xml'] = r'''<?xml version="1.0" encoding="utf-8"?>
<LinearLayout xmlns:android="http://schemas.android.com/apk/res/android"
    android:layout_width="76dp"
    android:layout_height="wrap_content"
    android:background="?attr/selectableItemBackground"
    android:clickable="true"
    android:focusable="true"
    android:gravity="center_horizontal"
    android:orientation="vertical"
    android:paddingTop="4dp"
    android:paddingBottom="4dp">

    <ImageView
        android:id="@+id/pillIcon"
        android:layout_width="70dp"
        android:layout_height="52dp"
        android:background="@drawable/bg_pill"
        android:importantForAccessibility="no"
        android:padding="14dp" />

    <TextView
        android:id="@+id/pillLabel"
        android:layout_width="wrap_content"
        android:layout_height="wrap_content"
        android:layout_marginTop="6dp"
        android:ellipsize="end"
        android:maxLines="1"
        android:textColor="@color/app_text"
        android:textSize="13sp" />
</LinearLayout>
'''

FILES['app/src/main/res/layout/view_dial_key.xml'] = r'''<?xml version="1.0" encoding="utf-8"?>
<LinearLayout xmlns:android="http://schemas.android.com/apk/res/android"
    android:layout_width="match_parent"
    android:layout_height="match_parent"
    android:background="@drawable/bg_key"
    android:clickable="true"
    android:focusable="true"
    android:gravity="center"
    android:orientation="vertical">

    <TextView
        android:id="@+id/keyDigit"
        android:layout_width="wrap_content"
        android:layout_height="wrap_content"
        android:textColor="@color/app_text"
        android:textSize="26sp" />

    <TextView
        android:id="@+id/keyLetters"
        android:layout_width="wrap_content"
        android:layout_height="wrap_content"
        android:textColor="@color/app_text_secondary"
        android:textSize="10sp" />
</LinearLayout>
'''

FILES['app/src/main/res/menu/bottom_nav.xml'] = r'''<?xml version="1.0" encoding="utf-8"?>
<menu xmlns:android="http://schemas.android.com/apk/res/android">
    <item
        android:id="@+id/nav_home"
        android:icon="@drawable/ic_home"
        android:title="Home" />
    <item
        android:id="@+id/nav_contacts"
        android:icon="@drawable/ic_people"
        android:title="Contacts" />
    <item
        android:id="@+id/nav_keypad"
        android:icon="@drawable/ic_dialpad"
        android:title="Keypad" />
</menu>
'''

FILES['app/src/main/res/values-night/colors.xml'] = r'''<?xml version="1.0" encoding="utf-8"?>
<resources>
    <color name="app_bg">#0F1514</color>
    <color name="app_surface">#1A2120</color>
    <color name="app_surface_variant">#2A3231</color>
    <color name="app_outline">#3F4948</color>
    <color name="app_text">#DEE4E2</color>
    <color name="app_text_secondary">#B0BBB9</color>
    <color name="app_accent">#4DDAD1</color>
    <color name="app_on_accent">#003735</color>
    <color name="app_accent_container">#1F4E4B</color>
    <color name="app_on_accent_container">#C7E9E5</color>
    <color name="app_star">#FFCA3A</color>
    <color name="app_danger">#FFB4AB</color>
    <color name="app_call">#81C995</color>
    <color name="app_on_call">#08240F</color>
    <color name="app_nav_bg">#18201F</color>
    <color name="app_sheet">#202928</color>
    <color name="app_tertiary">#FFB870</color>
    <color name="app_avatar_text">#1F2423</color>
</resources>
'''

FILES['app/src/main/res/values/colors.xml'] = r'''<?xml version="1.0" encoding="utf-8"?>
<resources>
    <color name="app_bg">#E5EEEC</color>
    <color name="app_surface">#F3F9F8</color>
    <color name="app_surface_variant">#DCE7E5</color>
    <color name="app_outline">#BFC9C7</color>
    <color name="app_text">#171D1C</color>
    <color name="app_text_secondary">#46514F</color>
    <color name="app_accent">#00696A</color>
    <color name="app_on_accent">#FFFFFF</color>
    <color name="app_accent_container">#C7E9E5</color>
    <color name="app_on_accent_container">#00201F</color>
    <color name="app_star">#F5A400</color>
    <color name="app_danger">#BA1A1A</color>
    <color name="app_call">#1E8E3E</color>
    <color name="app_on_call">#FFFFFF</color>
    <color name="app_nav_bg">#DEE8E6</color>
    <color name="app_sheet">#DAE6E4</color>
    <color name="app_tertiary">#8A5100</color>
    <color name="app_avatar_text">#1F2423</color>
</resources>
'''


def find_root():
    here = os.getcwd()
    for cand in (here, os.path.join(here, "FastContacts-upgraded")):
        if os.path.isfile(os.path.join(cand, "app", "src", "main", "AndroidManifest.xml")):
            return cand
    return None


def main():
    root = find_root()
    if root is None:
        print("ERROR: run this from the project folder (the one that contains the 'app' folder).")
        sys.exit(1)
    chk = os.path.join(root, "app", "src", "main", "java", "com", "example", "fastcontacts", "SearchEngine.kt")
    if not os.path.isfile(chk):
        print("ERROR: this does not look like the FastContacts project.")
        sys.exit(1)
    for rel, text in FILES.items():
        path = os.path.join(root, *rel.split("/"))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
        print("wrote", rel)
    print()
    print("Done: %d files written in %s" % (len(FILES), root))
    print("Next: git add . && git commit -m \"Material 3 UI\" && git push")


if __name__ == "__main__":
    main()
