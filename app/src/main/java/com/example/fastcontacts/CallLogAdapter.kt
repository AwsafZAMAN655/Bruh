package com.example.fastcontacts

import android.content.Context
import android.provider.CallLog
import android.text.format.DateUtils
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.ImageButton
import android.widget.TextView
import androidx.core.content.ContextCompat
import androidx.recyclerview.widget.DiffUtil
import androidx.recyclerview.widget.ListAdapter
import androidx.recyclerview.widget.RecyclerView

/** A small read-only model of a recent call. */
data class CallLogEntry(
    val name: String,
    val number: String,
    val dateMillis: Long,
    val type: Int,
    val durationSeconds: Long
)

object CallLogRepository {
    fun loadRecent(context: Context, limit: Int): List<CallLogEntry> {
        val result = ArrayList<CallLogEntry>()
        val projection = arrayOf(
            CallLog.Calls.CACHED_NAME,
            CallLog.Calls.NUMBER,
            CallLog.Calls.DATE,
            CallLog.Calls.TYPE,
            CallLog.Calls.DURATION
        )
        try {
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
                while (cursor.moveToNext() && result.size < limit) {
                    val number = if (numberCol >= 0) cursor.getString(numberCol).orEmpty() else ""
                    val name = if (nameCol >= 0) cursor.getString(nameCol).orEmpty() else ""
                    val date = if (dateCol >= 0) cursor.getLong(dateCol) else 0L
                    val type = if (typeCol >= 0) cursor.getInt(typeCol) else CallLog.Calls.MISSED_TYPE
                    val duration = if (durationCol >= 0) cursor.getLong(durationCol) else 0L
                    if (number.isNotBlank()) {
                        result.add(CallLogEntry(name.ifBlank { number }, number, date, type, duration))
                    }
                }
            }
        } catch (_: SecurityException) {
            // The user may deny call-log access; Contacts and Dialpad still work.
        } catch (_: IllegalArgumentException) {
            // Non-standard call-log provider should not crash the app.
        }
        return result
    }
}

class CallLogAdapter(
    private val onClick: (CallLogEntry) -> Unit
) : ListAdapter<CallLogEntry, CallLogAdapter.CallViewHolder>(Diff()) {

    private class Diff : DiffUtil.ItemCallback<CallLogEntry>() {
        override fun areItemsTheSame(a: CallLogEntry, b: CallLogEntry): Boolean =
            a.number == b.number && a.dateMillis == b.dateMillis && a.type == b.type

        override fun areContentsTheSame(a: CallLogEntry, b: CallLogEntry): Boolean = a == b
    }

    fun submit(items: List<CallLogEntry>) {
        submitList(items)
    }

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): CallViewHolder {
        val view = LayoutInflater.from(parent.context).inflate(R.layout.item_call_log, parent, false)
        return CallViewHolder(view)
    }

    override fun onBindViewHolder(holder: CallViewHolder, position: Int) {
        holder.bind(getItem(position), onClick)
    }

    class CallViewHolder(itemView: View) : RecyclerView.ViewHolder(itemView) {
        private val avatar: AvatarView = itemView.findViewById(R.id.callAvatar)
        private val name: TextView = itemView.findViewById(R.id.callName)
        private val number: TextView = itemView.findViewById(R.id.callNumber)
        private val meta: TextView = itemView.findViewById(R.id.callMeta)
        private val typeIcon: TextView = itemView.findViewById(R.id.callTypeIcon)
        private val callBtn: ImageButton = itemView.findViewById(R.id.callBtn)

        fun bind(entry: CallLogEntry, onClick: (CallLogEntry) -> Unit) {
            val context = itemView.context
            name.text = entry.name
            if (entry.name != entry.number && entry.number.isNotBlank()) {
                number.text = entry.number
                number.visibility = View.VISIBLE
            } else {
                number.visibility = View.GONE
            }

            // Initials-style avatar (no photo URI available from call log)
            avatar.bindPlain(entry.name, null)

            val (label, colorRes, arrow) = when (entry.type) {
                CallLog.Calls.OUTGOING_TYPE -> Triple("Outgoing", R.color.app_call, "↗")
                CallLog.Calls.INCOMING_TYPE -> Triple("Incoming", R.color.app_accent, "↙")
                CallLog.Calls.MISSED_TYPE -> Triple("Missed", R.color.app_danger, "↙")
                CallLog.Calls.REJECTED_TYPE -> Triple("Rejected", R.color.app_danger, "✗")
                CallLog.Calls.BLOCKED_TYPE -> Triple("Blocked", R.color.app_text_secondary, "⊘")
                else -> Triple("Call", R.color.app_text_secondary, "•")
            }
            val color = ContextCompat.getColor(context, colorRes)
            typeIcon.text = arrow
            typeIcon.setTextColor(color)

            val relative = if (entry.dateMillis > 0) {
                DateUtils.getRelativeTimeSpanString(
                    entry.dateMillis, System.currentTimeMillis(), DateUtils.MINUTE_IN_MILLIS
                ).toString()
            } else ""
            meta.text = listOf(label, relative).filter { it.isNotBlank() }.joinToString(" · ")
            if (entry.type == CallLog.Calls.MISSED_TYPE || entry.type == CallLog.Calls.REJECTED_TYPE) {
                name.setTextColor(color)
            } else {
                name.setTextColor(ContextCompat.getColor(context, R.color.app_text))
            }

            val callAction = View.OnClickListener { onClick(entry) }
            itemView.setOnClickListener(callAction)
            callBtn.setOnClickListener(callAction)
            itemView.contentDescription = "${entry.name}, $label, tap to call"
        }
    }
}
