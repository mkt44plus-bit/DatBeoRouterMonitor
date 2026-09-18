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
import java.net.URLEncoder
import java.util.concurrent.Executors

class MainActivity : Activity() {
    private val executor = Executors.newSingleThreadExecutor()
    private lateinit var ip: EditText
    private lateinit var key: EditText
    private lateinit var status: TextView
    private lateinit var out: TextView

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        buildUi()
    }

    private fun buildUi() {
        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(24, 24, 24, 24)
            setBackgroundColor(Color.WHITE)
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
            text = "OpenWrt • NetBird • Traffic Monitor"
            textSize = 14f
            setTextColor(Color.DKGRAY)
            setPadding(0, 4, 0, 12)
        })

        ip = EditText(this).apply {
            hint = "NetBird IP của router"
            setSingleLine(true)
            setText("100.81.163.26")
        }

        key = EditText(this).apply {
            hint = "API key trên OpenWrt"
            setSingleLine(true)
            setTextColor(Color.BLACK)
        }

        content.addView(ip)
        content.addView(key)

        content.addView(Button(this).apply {
            text = "KIỂM TRA KẾT NỐI"
            setOnClickListener { load() }
        })

        status = TextView(this).apply {
            text = "Sẵn sàng"
            textSize = 16f
            setTextColor(Color.BLACK)
            setPadding(0, 16, 0, 8)
        }
        content.addView(status)

        out = TextView(this).apply {
            text = "Kết quả sẽ hiện ở đây."
            textSize = 14f
            setTextColor(Color.BLACK)
            setPadding(0, 8, 0, 0)
        }
        content.addView(out)

        root.addView(scroll, ViewGroup.LayoutParams(-1, -1))
        setContentView(root)
    }

    private fun load() {
        val host = ip.text.toString().trim()
        val apiKey = key.text.toString().trim()

        if (host.isEmpty()) {
            status.text = "Thiếu IP NetBird"
            out.text = "Nhập IP NetBird của OpenWrt."
            return
        }

        if (apiKey.isEmpty()) {
            status.text = "Thiếu API key"
            out.text = "Nhập key trong /etc/datbeo-router-monitor/api_key"
            return
        }

        val cleanHost = host
            .removePrefix("http://")
            .removePrefix("https://")
            .trimEnd('/')

        val encodedKey = URLEncoder.encode(apiKey, "UTF-8")
        val endpoint = "http://" + cleanHost + "/cgi-bin/datbeo-traffic?key=" + encodedKey

        status.text = "Đang kết nối..."
        out.text = "Router: " + cleanHost + "\nĐang gọi API..."

        executor.execute {
            var conn: HttpURLConnection? = null
            try {
                conn = (URL(endpoint).openConnection() as HttpURLConnection).apply {
                    requestMethod = "GET"
                    connectTimeout = 10000
                    readTimeout = 10000
                    doInput = true
                    useCaches = false
                    setRequestProperty("Accept", "application/json")
                    setRequestProperty("Connection", "close")
                    setRequestProperty("X-API-Key", apiKey)
                }

                val code = conn.responseCode
                val stream = if (code in 200..299) conn.inputStream else conn.errorStream
                val body = stream?.bufferedReader()?.use { it.readText() } ?: ""

                if (code !in 200..299) {
                    throw Exception("HTTP " + code + "\n" + body.take(3000))
                }

                val json = try {
                    JSONObject(body)
                } catch (jsonErr: Exception) {
                    throw Exception(
                        "JSON không hợp lệ: " + (jsonErr.message ?: "unknown") +
                        "\n\nResponse:\n" + body.take(3000)
                    )
                }

                if (json.optString("error").isNotBlank()) {
                    throw Exception("API: " + json.optString("error"))
                }

                val result = StringBuilder()
                result.append("✅ API hoạt động\n\n")
                result.append("Router: ").append(json.optString("hostname", "-")).append("\n")
                result.append("NetBird: ").append(json.optString("netbird_ip", "-")).append("\n")
                result.append("LAN: ").append(json.optString("lan", "-")).append("\n\n")
                result.append("TRAFFIC\n")
                appendTraffic(result, json.opt("traffic"))

                result.append("\nDEVICES\n")
                val leases = json.optJSONArray("leases")
                if (leases != null) {
                    for (i in 0 until leases.length()) {
                        val d = leases.getJSONObject(i)
                        result.append(d.optString("name", "Unknown"))
                            .append("  ").append(d.optString("ip", "-"))
                            .append("  ").append(d.optString("mac", "-")).append("\n")
                    }
                }

                runOnUiThread {
                    status.text = "✅ Kết nối thành công (HTTP " + code + ")"
                    out.text = result.toString()
                }
            } catch (err: Exception) {
                runOnUiThread {
                    status.text = "❌ Kết nối thất bại"
                    out.text = "URL: " + endpoint + "\n\n" +
                        (err.message ?: err.javaClass.simpleName)
                }
            } finally {
                conn?.disconnect()
            }
        }
    }

    private fun appendTraffic(out: StringBuilder, raw: Any?) {
        if (raw is JSONArray) {
            for (i in 0 until raw.length()) {
                val item = raw.opt(i)
                if (item is JSONObject) appendTrafficRow(out, item)
            }
            return
        }

        if (raw is JSONObject) {
            val cols = raw.optJSONArray("columns")
            val data = raw.optJSONArray("data")
            if (cols != null && data != null) {
                val macIndex = firstColIndex(cols, arrayOf("mac", "host"))
                val connsIndex = firstColIndex(cols, arrayOf("conns", "connections"))
                val rxIndex = firstColIndex(cols, arrayOf("rx_bytes", "download", "rx"))
                val txIndex = firstColIndex(cols, arrayOf("tx_bytes", "upload", "tx"))

                for (i in 0 until data.length()) {
                    val row = data.optJSONArray(i) ?: continue
                    val item = JSONObject()
                    if (macIndex >= 0) item.put("mac", row.optString(macIndex))
                    if (connsIndex >= 0) item.put("conns", row.optLong(connsIndex))
                    if (rxIndex >= 0) item.put("rx_bytes", row.optLong(rxIndex))
                    if (txIndex >= 0) item.put("tx_bytes", row.optLong(txIndex))
                    appendTrafficRow(out, item)
                }
            }
        }
    }

    private fun appendTrafficRow(out: StringBuilder, item: JSONObject) {
        out.append(item.optString("mac", "-"))
            .append("  ↓ ").append(formatBytes(item.optLong("rx_bytes", 0)))
            .append("  ↑ ").append(formatBytes(item.optLong("tx_bytes", 0)))
            .append("  · ").append(item.optLong("conns", 0)).append(" conn\n")
    }

    private fun firstColIndex(columns: JSONArray, names: Array<String>): Int {
        for (name in names) {
            for (i in 0 until columns.length()) {
                if (columns.optString(i).equals(name, ignoreCase = true)) return i
            }
        }
        return -1
    }

    private fun formatBytes(value: Long): String {
        var n = value.toDouble()
        val units = arrayOf("B", "KB", "MB", "GB", "TB")
        var i = 0
        while (n >= 1024 && i < units.lastIndex) {
            n /= 1024
            i++
        }
        return if (i == 0) value.toString() + " B" else String.format("%.2f %s", n, units[i])
    }

    override fun onDestroy() {
        executor.shutdownNow()
        super.onDestroy()
    }
}
