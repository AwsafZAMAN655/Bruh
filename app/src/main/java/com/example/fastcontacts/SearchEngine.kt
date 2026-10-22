package com.example.fastcontacts

/**
 * Smart relevance search with a precomputed index so each keystroke avoids
 * repeated lowercasing, digit filtering, and unnecessary allocations.
 *
 * Names come from Android's StructuredName (given / family), never from
 * splitting the display name.
 */
class SearchEngine(private val contacts: List<Contact>) {

    /** Pre-normalized fields built once per contact list snapshot. */
    private data class Indexed(
        val contact: Contact,
        val full: String,
        val first: String,
        val last: String,
        val phoneDigits: List<String>,
        val emailLower: List<String>,
        val company: String,
        val nickname: String,
        val jobTitle: String
    )

    private val index: List<Indexed> = contacts.map { c ->
        Indexed(
            contact = c,
            full = c.name.lowercase().trim(),
            first = c.firstName.lowercase(),
            last = c.lastName.lowercase(),
            phoneDigits = c.phones.map { it.number.filter { ch -> ch.isDigit() } },
            emailLower = c.emails.map { it.address.lowercase() },
            company = c.company.lowercase(),
            nickname = c.nickname.lowercase(),
            jobTitle = c.jobTitle.lowercase()
        )
    }

    fun search(query: String): List<Contact> {
        val q = query.lowercase().trim()
        if (q.isBlank()) return contacts

        val phoneLike = q.all { it.isDigit() || it == '+' || it == '-' || it == '(' || it == ')' || it == ' ' }
        val qDigits = if (phoneLike) q.filter { it.isDigit() } else ""

        val scored = ArrayList<IndexedContact>(minOf(64, index.size))
        for (i in index.indices) {
            val t = tier(index[i], q, qDigits)
            if (t >= 0) scored.add(IndexedContact(t, i))
        }

        scored.sortWith(
            compareBy(
                { it.tier },
                { index[it.idx].first },
                { index[it.idx].full }
            )
        )
        return scored.map { index[it.idx].contact }
    }

    private class IndexedContact(val tier: Int, val idx: Int)

    private fun tier(ix: Indexed, q: String, qDigits: String): Int {
        val first = ix.first
        val last = ix.last
        val full = ix.full
        return when {
            first == q -> 0
            first.startsWith(q) -> 1
            first.contains(q) -> 2
            last.isNotEmpty() && last.startsWith(q) -> 3
            full.startsWith(q) -> 4
            full.contains(q) -> 5
            qDigits.isNotEmpty() && ix.phoneDigits.any { phoneDigitsMatch(it, qDigits) } -> 6
            ix.emailLower.any { it.contains(q) } -> 7
            ix.company.contains(q) || ix.nickname.contains(q) || ix.jobTitle.contains(q) -> 8
            else -> -1
        }
    }

    companion object {
        /**
         * +880 1712-345678, 01712345678 and 01712 345678 all match "017123" / "1712".
         * Operates on already digit-filtered strings.
         */
        fun phoneDigitsMatch(numberDigits: String, qDigits: String): Boolean {
            if (numberDigits.contains(qDigits)) return true
            val stripped = qDigits.trimStart('0')
            return stripped.length >= 3 && numberDigits.contains(stripped)
        }

        fun phoneMatches(number: String, qDigits: String): Boolean {
            val nd = number.filter { it.isDigit() }
            return phoneDigitsMatch(nd, qDigits)
        }

        private fun key(c: Contact, byLast: Boolean): String {
            val k = if (byLast) {
                (if (c.lastName.isNotEmpty()) c.lastName else c.firstName) + " " + c.firstName
            } else {
                (if (c.firstName.isNotEmpty()) c.firstName else c.name) + " " + c.lastName
            }.trim().lowercase()
            // names that do not start with a letter go to the end ("#" section)
            return (if (k.firstOrNull()?.isLetter() == true) "a" else "b") + k
        }

        fun sorted(list: List<Contact>, byLast: Boolean): List<Contact> =
            list.sortedBy { key(it, byLast) }

        fun letterOf(c: Contact, byLast: Boolean): String {
            val k = key(c, byLast).substring(1).trim()
            val ch = k.firstOrNull() ?: return "#"
            return if (ch.isLetter()) ch.uppercase() else "#"
        }
    }
}
