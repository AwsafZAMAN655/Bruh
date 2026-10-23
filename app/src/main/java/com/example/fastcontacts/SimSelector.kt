package com.example.fastcontacts

import android.Manifest
import android.annotation.SuppressLint
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Bundle
import android.telecom.PhoneAccountHandle
import android.telecom.TelecomManager
import android.view.LayoutInflater
import android.widget.LinearLayout
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AlertDialog
import androidx.core.content.ContextCompat

object SimSelector {

    @SuppressLint("MissingPermission")
    fun makeCall(context: Context, phoneNumber: String) {
        if (phoneNumber.isBlank()) {
            Toast.makeText(context, "Invalid phone number", Toast.LENGTH_SHORT).show()
            return
        }

        val telecomManager = context.getSystemService(Context.TELECOM_SERVICE) as? TelecomManager
        val hasPhoneStatePerm = ContextCompat.checkSelfPermission(context, Manifest.permission.READ_PHONE_STATE) == PackageManager.PERMISSION_GRANTED

        if (telecomManager == null || !hasPhoneStatePerm) {
            fallbackCall(context, phoneNumber, null)
            return
        }

        try {
            val accounts = telecomManager.callCapablePhoneAccounts
            if (accounts.isNullOrEmpty() || accounts.size == 1) {
                fallbackCall(context, phoneNumber, accounts?.firstOrNull())
                return
            }

            val dialogView = LayoutInflater.from(context).inflate(R.layout.dialog_sim_picker, null)
            val container = dialogView.findViewById<LinearLayout>(R.id.simContainer)
            container.removeAllViews()

            val dialog = AlertDialog.Builder(context)
                .setTitle("Select SIM for Call")
                .setView(dialogView)
                .create()

            for ((index, account) in accounts.withIndex()) {
                val label = try {
                    telecomManager.getPhoneAccount(account)?.label?.toString() ?: "SIM ${index + 1}"
                } catch (_: Exception) {
                    "SIM ${index + 1}"
                }

                val row = TextView(context).apply {
                    text = "📶  $label"
                    textSize = 16f
                    setPadding(32, 28, 32, 28)
                    setTextColor(ContextCompat.getColor(context, R.color.app_text))
                    val typedValue = android.util.TypedValue()
                    context.theme.resolveAttribute(android.R.attr.selectableItemBackground, typedValue, true)
                    setBackgroundResource(typedValue.resourceId)
                    setOnClickListener {
                        dialog.dismiss()
                        placeTelecomCall(context, telecomManager, account, phoneNumber)
                    }
                }
                container.addView(row)
            }

            dialog.show()
        } catch (_: Exception) {
            fallbackCall(context, phoneNumber, null)
        }
    }

    @SuppressLint("MissingPermission")
    private fun placeTelecomCall(context: Context, telecomManager: TelecomManager, account: PhoneAccountHandle, number: String) {
        try {
            val uri = Uri.parse("tel:$number")
            val extras = Bundle().apply {
                putParcelable(TelecomManager.EXTRA_PHONE_ACCOUNT_HANDLE, account)
            }
            if (ContextCompat.checkSelfPermission(context, Manifest.permission.CALL_PHONE) == PackageManager.PERMISSION_GRANTED) {
                telecomManager.placeCall(uri, extras)
            } else {
                fallbackCall(context, number, account)
            }
        } catch (_: Exception) {
            fallbackCall(context, number, account)
        }
    }

    private fun fallbackCall(context: Context, number: String, account: PhoneAccountHandle?) {
        val intent = Intent(Intent.ACTION_CALL, Uri.parse("tel:$number")).apply {
            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            if (account != null) {
                putExtra("android.telecom.extra.PHONE_ACCOUNT_HANDLE", account)
            }
        }
        try {
            context.startActivity(intent)
        } catch (_: Exception) {
            Toast.makeText(context, "Call permission required", Toast.LENGTH_SHORT).show()
        }
    }
}
