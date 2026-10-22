
package com.example.fastcontacts

import android.os.Handler
import android.os.Looper
import android.view.LayoutInflater
import android.view.MotionEvent
import android.view.View
import android.widget.GridLayout
import android.widget.ImageButton
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView
import java.util.concurrent.Executors
import java.util.concurrent.atomic.AtomicInteger

class DialpadController(
    private val activity: AppCompatActivity,
    root: View,
    openContact: (Contact) -> Unit
) {
    private val number = StringBuilder()

    private val display: TextView =
        root.findViewById(R.id.dialDisplay)

    private val recentSection: View =
        root.findViewById(R.id.recentSection)

    private val matchesTitle: View =
        root.findViewById(R.id.matchesTitle)

    private val keypad: GridLayout =
        root.findViewById(R.id.keypad)

    private val toggleKeypad: TextView =
        root.findViewById(R.id.btnToggleKeypad)

    private val dialMatches: RecyclerView =
        root.findViewById(R.id.dialMatches)

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

    init {
        dialMatches.layoutManager = LinearLayoutManager(activity)
        dialMatches.adapter = adapter

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
                Ui.dp(activity, 6),
                Ui.dp(activity, 4),
                Ui.dp(activity, 6),
                Ui.dp(activity, 4)
            )

            keyView.layoutParams = params
            keyView.contentDescription = digit

            keyView.setOnTouchListener { view, event ->
                when (event.actionMasked) {
                    MotionEvent.ACTION_DOWN -> {
                        view.animate()
                            .scaleX(0.92f)
                            .scaleY(0.92f)
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

            toggleKeypad.text = if (isVisible) {
                "Show keypad"
            } else {
                "Hide keypad"
            }

            toggleKeypad.contentDescription = if (isVisible) {
                "Show dialpad"
            } else {
                "Hide dialpad"
            }

            dialMatches.requestLayout()
            recentSection.requestLayout()
        }

        root.findViewById<ImageButton>(R.id.btnDialCall)
            .setOnClickListener {
                if (number.isNotEmpty()) {
                    Actions.call(activity, number.toString())
                }
            }

        root.findViewById<ImageButton>(R.id.btnAddContact)
            .setOnClickListener {
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

    fun dispose() {
        pendingSearch?.let(handler::removeCallbacks)
        searchExecutor.shutdownNow()
    }

    private fun refresh() {
        val query = number.toString()

        display.text = query
        display.textSize = if (number.length > 14) 24f else 32f

        val searching = query.isNotEmpty()

        if (!searching) {
            recentSection.visibility = View.VISIBLE
            matchesTitle.visibility = View.GONE
            dialMatches.visibility = View.GONE

            pendingSearch?.let(handler::removeCallbacks)
            searchGeneration.incrementAndGet()
            adapter.submit(emptyList())
            return
        }

        // Keep the results area as flexible space above the keypad.
        // This prevents the keypad from jumping upward when typing.
        recentSection.visibility = View.GONE
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
