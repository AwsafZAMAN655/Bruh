package com.example.fastcontacts

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
