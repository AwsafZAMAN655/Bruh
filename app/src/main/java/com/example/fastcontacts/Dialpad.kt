package com.example.fastcontacts

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
