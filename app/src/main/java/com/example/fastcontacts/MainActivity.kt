package com.example.fastcontacts

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.transition.TransitionManager
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.Button
import android.widget.EditText
import android.widget.ImageButton
import android.widget.ImageView
import android.widget.PopupMenu
import android.widget.TextView
import androidx.activity.result.contract.ActivityResultContracts
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
    private lateinit var paneContacts: View
    private lateinit var paneDialpad: View
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
    // 0 = Phone, 1 = Contacts
    private var tab = 0
    private val mainHandler = Handler(Looper.getMainLooper())
    private var filterRunnable: Runnable? = null
    private var loadGeneration = 0
    private var filterGeneration = 0
    private val filterExecutor = Executors.newSingleThreadExecutor()
    private lateinit var callLogAdapter: CallLogAdapter
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
        paneContacts = findViewById(R.id.paneContacts)
        paneDialpad = findViewById(R.id.paneDialpad)
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
        callLogAdapter = CallLogAdapter { entry ->
            if (entry.number.isNotBlank()) Actions.call(this, entry.number)
        }
        findViewById<RecyclerView>(R.id.recentCalls).apply {
            layoutManager = LinearLayoutManager(this@MainActivity)
            adapter = callLogAdapter
            isNestedScrollingEnabled = true
        }
        findViewById<TextView>(R.id.recentCallsEmpty).setOnClickListener {
            if (!hasCallLogPermission()) requestCallLogPermission()
        }

        search.doAfterTextChanged {
            btnClear.visibility = if (it.isNullOrEmpty()) View.GONE else View.VISIBLE
            filterRunnable?.let(mainHandler::removeCallbacks)
            val task = Runnable { applyFilter() }
            filterRunnable = task
            mainHandler.postDelayed(task, 50L)
        }
        btnClear.setOnClickListener { search.setText("") }

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
                R.id.nav_phone -> showTab(0)
                R.id.nav_contacts -> showTab(1)
            }
            true
        }

        if (!hasContactsPermission()) requestPermissions()
        else if (hasCallLogPermission()) loadCallLog()
        else requestCallLogPermission()
        showTab(0)
        if (!hasCallLogPermission()) {
            findViewById<RecyclerView>(R.id.recentCalls).visibility = View.GONE
            findViewById<TextView>(R.id.recentCallsEmpty).apply {
                text = "Tap here to allow call history access"
                visibility = View.VISIBLE
            }
        }
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
        val recentList = findViewById<RecyclerView>(R.id.recentCalls)
        val recentEmpty = findViewById<TextView>(R.id.recentCallsEmpty)
        if (!hasCallLogPermission()) {
            recentList.visibility = View.GONE
            recentEmpty.text = "Tap here to allow call history access"
            recentEmpty.visibility = View.VISIBLE
            return
        }
        Thread {
            val entries = CallLogRepository.loadRecent(this, 40)
            runOnUiThread {
                if (isFinishing || isDestroyed) return@runOnUiThread
                callLogAdapter.submit(entries)
                recentList.visibility = if (entries.isEmpty()) View.GONE else View.VISIBLE
                recentEmpty.text = if (entries.isEmpty()) "No recent calls yet" else ""
                recentEmpty.visibility = if (entries.isEmpty()) View.VISIBLE else View.GONE
            }
        }.start()
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
        header.visibility = if (t == 0) View.GONE else View.VISIBLE
        updateChipsVisibility()
        if (t == 0) fab.hide() else fab.show()
        swap(paneDialpad, t == 0)
        swap(paneContacts, t == 1)
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
                rebuildChips()
                applyFilter()
                dialpad.setContacts(sorted)
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
            emptyPermission.visibility = View.VISIBLE
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
