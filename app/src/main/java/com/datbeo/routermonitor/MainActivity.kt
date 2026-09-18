package com.datbeo.routermonitor

import android.app.Activity
import android.os.Bundle
import android.graphics.Color
import android.view.ViewGroup
import android.widget.*
import org.json.JSONArray
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.util.concurrent.Executors

class MainActivity : Activity() {
    private val executor = Executors.newSingleThreadExecutor()
    private lateinit var ip: EditText
    private lateinit var key: EditText
    private lateinit var out: TextView

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        buildUi()
    }

    private fun buildUi() {
        val box = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(24, 24, 24, 24)
        }
        val scroll = ScrollView(this)
        val content = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
        scroll.addView(content)

        content.addView(TextView(this).apply {
            text = "DatBeo Router Monitor"
            textSize = 26f
            setTextColor(Color.BLACK)
        })
        content.addView(TextView(this).apply {
            text = "OpenWrt traffic via NetBird"
            textSize = 14f
            setPadding(0, 4, 0, 12)
        })

        ip = EditText(this).apply {
            hint = "NetBird IP, ví dụ 100.81.163.26"
            setSingleLine(true)
        }
        key = EditText(this).apply {
            hint = "OpenWrt API key"
            setSingleLine(true)
        }
        content.addView(ip)
        content.addView(key)

        content.addView(Button(this).apply {
            text = "Kết nối / Làm mới"
            setOnClickListener { load() }
        })

        out = TextView(this).apply {
            text = "Chưa kết nối"
            textSize = 15f
            setPadding(0, 20, 0, 0)
        }
        content.addView(out)

        box.addView(scroll, ViewGroup.LayoutParams(-1, -1))
        setContentView(box)
    }

    private fun load() {
        val host = ip.text.toString().trim()
        val apiKey = key.text.toString().trim()
        if (host.isEmpty() || apiKey.isEmpty()) {
            out.text = "Hãy nhập NetBird IP và API key."
            return
        }

        out.text = "Đang kết nối..."
        executor.execute {
            try {
                val base = if (host.startsWith("http://") || host.startsWith("https://")) host else "http://$host"
                val conn = (URL("$base/cgi-bin/datbeo-traffic").openConnection() as HttpURLConnection).apply {
                    requestMethod = "GET"
                    connectTimeout = 5000
                    readTimeout = 7000
                    setRequestProperty("X-API-Key", apiKey)
                }
                val code = conn.responseCode
                val body = (if (code in 200..299) conn.inputStream else conn.errorStream)
                    .bufferedReader().use { it.readText() }
                if (code !in 200..299) throw Exception("HTTP $code")

                val json = JSONObject(body)
                if (json.optString("error").isNotBlank()) throw Exception(json.optString("error"))

                val result = StringBuilder()
                result.append("Router: ").append(json.optString("hostname", "OpenWrt"))
                    .append("\nNetBird: ").append(json.optString("netbird_ip", "-"))
                    .append("\nLAN: ").append(json.optString("lan", "-"))
                    .append("\n\nTRAFFIC\n")
                appendTraffic(result, json.opt("traffic"))

                result.append("\nDEVICES\n")
                val leases = json.optJSONArray("leases")
                if (leases != null) {
                    for (i in 0 until leases.length()) {
                        val item = leases.getJSONObject(i)
                        result.append(item.optString("name", "Unknown"))
                            .append("  ").append(item.optString("ip", "-"))
                            .append("  ").append(item.optString("mac", "-")).append("\n")
                    }
                }
                runOnUiThread { out.text = result.toString() }
            } catch (err: Exception) {
                runOnUiThread { out.text = "Lỗi: " + err.message }
            }
        }
    }

    private fun appendTraffic(out: StringBuilder, raw: Any?) {
        if (raw is JSONArray) {
            for (i in 0 until raw.length()) {
                val item = raw.opt(i)
                if (item is JSONObject) {
                    out.append(item.optString("mac", "-"))
                        .append("  ↓ ").append(formatBytes(item.optLong("rx_bytes", 0)))
                        .append("  ↑ ").append(formatBytes(item.optLong("tx_bytes", 0)))
                        .append("  · ").append(item.optLong("conns", 0)).append(" conn\n")
                }
            }
            return
        }

        if (raw is JSONObject) {
            val cols = raw.optJSONArray("columns") ?: return
            val data = raw.optJSONArray("data") ?: return
            val macIndex = colIndex(cols, "mac")
            val connsIndex = colIndex(cols, "conns")
            val rxIndex = colIndex(cols, "rx_bytes")
            val txIndex = colIndex(cols, "tx_bytes")

            for (i in 0 until data.length()) {
                val row = data.optJSONArray(i) ?: continue
                val mac = if (macIndex >= 0) row.optString(macIndex) else "-"
                val conns = if (connsIndex >= 0) row.optLong(connsIndex) else 0
                val rx = if (rxIndex >= 0) row.optLong(rxIndex) else 0
                val tx = if (txIndex >= 0) row.optLong(txIndex) else 0
                out.append(mac).append("  ↓ ").append(formatBytes(rx))
                    .append("  ↑ ").append(formatBytes(tx))
                    .append("  · ").append(conns).append(" conn\n")
            }
        }
    }

    private fun colIndex(columns: JSONArray, wanted: String): Int {
        for (i in 0 until columns.length()) {
            if (columns.optString(i).equals(wanted, ignoreCase = true)) return i
        }
        return -1
    }

    private fun formatBytes(value: Long): String {
        var n = value.toDouble()
        val units = arrayOf("B", "KB", "MB", "GB", "TB")
        var i = 0
        while (n >= 1024 && i < units.lastIndex) { n /= 1024; i++ }
        return if (i == 0) "${value} B" else String.format("%.2f %s", n, units[i])
    }

    override fun onDestroy() {
        executor.shutdownNow()
        super.onDestroy()
    }
}
