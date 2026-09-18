package com.datbeo.routermonitor

import android.app.Activity
import android.graphics.Color
import android.graphics.Typeface
import android.graphics.drawable.GradientDrawable
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.text.InputType
import android.view.Gravity
import android.view.View
import android.view.ViewGroup
import android.widget.*
import org.json.JSONArray
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.net.URLEncoder
import java.util.concurrent.Executors

data class DeviceInfo(
    val name: String,
    val ip: String,
    val mac: String,
    val rx: Long,
    val tx: Long,
    val conns: Long
)

data class SiteVisit(
    val time: String,
    val domain: String,
    val ip: String
)

class MainActivity : Activity() {
    private val executor = Executors.newSingleThreadExecutor()
    private val handler = Handler(Looper.getMainLooper())

    private lateinit var root: FrameLayout
    private lateinit var ipInput: EditText
    private lateinit var keyInput: EditText
    private lateinit var statusView: TextView
    private lateinit var contentView: LinearLayout

    private var routerIp = "100.81.163.26"
    private var apiKey = ""
    private var devices = listOf<DeviceInfo>()
    private var sites = listOf<SiteVisit>()
    private var connected = false
    private var lastUpdated = ""

    private val refreshRunnable = object : Runnable {
        override fun run() {
            if (connected) {
                fetchData(false)
                handler.postDelayed(this, 3000)
            }
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        window.statusBarColor = Color.rgb(190, 12, 111)
        window.navigationBarColor = Color.rgb(190, 12, 111)
        root = FrameLayout(this)
        setContentView(root)
        showLogin()
    }

    override fun onBackPressed() {
        if (connected) showDashboard() else super.onBackPressed()
    }

    private fun showLogin() {
        connected = false
        handler.removeCallbacks(refreshRunnable)
        root.removeAllViews()

        val screen = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            gravity = Gravity.CENTER_HORIZONTAL
            setPadding(28.dp(), 68.dp(), 28.dp(), 28.dp())
            background = pinkGradient()
        }

        val title = TextView(this).apply {
            text = "Đạt Béo Traffic"
            textSize = 43f
            typeface = Typeface.create(Typeface.SERIF, Typeface.ITALIC)
            setTextColor(Color.WHITE)
            gravity = Gravity.CENTER
        }
        screen.addView(title, LinearLayout.LayoutParams(-1, 110.dp()))

        ipInput = EditText(this).apply {
            hint = "IP"
            setText(routerIp)
            textSize = 18f
            gravity = Gravity.CENTER
            setSingleLine(true)
            setTextColor(Color.WHITE)
            setHintTextColor(0xCCFFFFFF.toInt())
            background = glassEditBackground()
            setPadding(22.dp(), 0, 22.dp(), 0)
        }
        screen.addView(ipInput, fieldParams())

        keyInput = EditText(this).apply {
            hint = "KEY"
            inputType = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_PASSWORD
            gravity = Gravity.CENTER
            setSingleLine(true)
            textSize = 18f
            setTextColor(Color.WHITE)
            setHintTextColor(0xCCFFFFFF.toInt())
            background = glassEditBackground()
            setPadding(22.dp(), 0, 22.dp(), 0)
        }
        screen.addView(keyInput, fieldParams())

        val login = Button(this).apply {
            text = "Log In"
            textSize = 16f
            setTextColor(Color.WHITE)
            background = outlineButton()
            setOnClickListener {
                routerIp = ipInput.text.toString().trim()
                apiKey = keyInput.text.toString().trim()
                if (routerIp.isEmpty() || apiKey.isEmpty()) {
                    toast("Nhập IP và KEY")
                    return@setOnClickListener
                }
                connected = true
                showDashboard()
                fetchData(true)
                handler.removeCallbacks(refreshRunnable)
                handler.postDelayed(refreshRunnable, 3000)
            }
        }
        screen.addView(login, LinearLayout.LayoutParams(-1, 58.dp()).apply {
            topMargin = 14.dp()
        })

        root.addView(screen, FrameLayout.LayoutParams(-1, -1))
    }

    private fun showDashboard() {
        root.removeAllViews()

        val scroll = ScrollView(this)
        contentView = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(18.dp(), 12.dp(), 18.dp(), 78.dp())
            background = pinkGradient()
        }
        scroll.addView(contentView)

        contentView.addView(TextView(this).apply {
            text = "Đạt Béo Traffic"
            textSize = 33f
            typeface = Typeface.create(Typeface.SERIF, Typeface.ITALIC)
            setTextColor(Color.WHITE)
            gravity = Gravity.CENTER
            setPadding(0, 6.dp(), 0, 2.dp())
        })

        statusView = TextView(this).apply {
            text = "● Đang kết nối"
            textSize = 14f
            gravity = Gravity.CENTER
            setTextColor(0xFF8BFFB0.toInt())
            setPadding(0, 0, 0, 5.dp())
        }
        contentView.addView(statusView)

        contentView.addView(TextView(this).apply {
            text = "OpenWrt Router  •  NetBird"
            textSize = 14f
            setTextColor(0xEEFFFFFF.toInt())
            gravity = Gravity.CENTER
        })

        contentView.addView(pill("◎  " + routerIp))

        contentView.addView(summaryCard())

        val head = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
            setPadding(6.dp(), 16.dp(), 6.dp(), 6.dp())
        }
        head.addView(TextView(this).apply {
            text = "Thiết bị"
            textSize = 22f
            typeface = Typeface.DEFAULT_BOLD
            setTextColor(Color.WHITE)
        }, LinearLayout.LayoutParams(0, -2, 1f))
        head.addView(TextView(this).apply {
            text = "Cập nhật " + if (lastUpdated.isEmpty()) "--:--" else lastUpdated
            textSize = 11f
            setTextColor(0xDDFFFFFF.toInt())
        })
        contentView.addView(head)

        if (devices.isEmpty()) {
            contentView.addView(card(TextView(this).apply {
                text = "Đang chờ dữ liệu traffic..."
                textSize = 15f
                setTextColor(Color.WHITE)
                setPadding(10.dp(), 12.dp(), 10.dp(), 12.dp())
            }))
        } else {
            devices.sortedByDescending { it.rx + it.tx }.forEach { d ->
                contentView.addView(deviceCard(d))
            }
        }

        val webHead = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
            setPadding(6.dp(), 14.dp(), 6.dp(), 6.dp())
        }
        webHead.addView(TextView(this).apply {
            text = "Website đã truy cập"
            textSize = 22f
            typeface = Typeface.DEFAULT_BOLD
            setTextColor(Color.WHITE)
        }, LinearLayout.LayoutParams(0, -2, 1f))
        webHead.addView(TextView(this).apply {
            text = "Xem tất cả  ›"
            textSize = 13f
            setTextColor(Color.WHITE)
            setOnClickListener { showWebsitePage(null) }
        })
        contentView.addView(webHead)
        contentView.addView(websiteCard(null))
        contentView.addView(bottomNav())

        root.addView(scroll, FrameLayout.LayoutParams(-1, -1))
    }

    private fun summaryCard(): View {
        val row = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER
            background = glassCard()
        }

        val totalRx = devices.sumOf { it.rx }
        val totalTx = devices.sumOf { it.tx }

        row.addView(metric("↓", "Tải xuống", formatBytes(totalRx)))
        row.addView(metric("↑", "Tải lên", formatBytes(totalTx)))
        row.addView(metric("●", "Thiết bị online", devices.size.toString() + ""))

        return row.withMargins(0, 14.dp(), 0, 7.dp())
    }

    private fun metric(icon: String, label: String, value: String): View {
        val box = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            gravity = Gravity.CENTER
            setPadding(2.dp(), 12.dp(), 2.dp(), 12.dp())
        }
        box.addView(TextView(this).apply {
            text = icon
            textSize = 25f
            gravity = Gravity.CENTER
            setTextColor(Color.WHITE)
        })
        box.addView(TextView(this).apply {
            text = label
            textSize = 11f
            gravity = Gravity.CENTER
            setTextColor(0xEEFFFFFF.toInt())
        })
        box.addView(TextView(this).apply {
            text = value
            textSize = 18f
            typeface = Typeface.DEFAULT_BOLD
            gravity = Gravity.CENTER
            setTextColor(Color.WHITE)
        })
        return box.withWeight(1f)
    }

    private fun deviceCard(d: DeviceInfo): View {
        val row = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
            setPadding(12.dp(), 12.dp(), 12.dp(), 12.dp())
            background = glassCard()
            setOnClickListener { showDevicePage(d) }
        }

        row.addView(TextView(this).apply {
            text = deviceIcon(d.name)
            textSize = 24f
            gravity = Gravity.CENTER
            setTextColor(Color.WHITE)
            background = GradientDrawable(
                GradientDrawable.Orientation.TL_BR,
                intArrayOf(0xFFA85CE6.toInt(), 0xFFF05BAA.toInt())
            ).apply { cornerRadius = 60f }
        }, LinearLayout.LayoutParams(54.dp(), 54.dp()).apply {
            rightMargin = 10.dp()
        })

        val middle = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
        middle.addView(TextView(this).apply {
            text = if (d.name.isEmpty()) "Thiết bị" else d.name
            textSize = 16f
            typeface = Typeface.DEFAULT_BOLD
            setTextColor(Color.WHITE)
        })
        middle.addView(TextView(this).apply {
            text = if (d.ip.isEmpty()) d.mac else d.ip
            textSize = 12f
            setTextColor(0xE8FFFFFF.toInt())
        })
        middle.addView(TextView(this).apply {
            text = "● Online  •  " + d.conns + " kết nối"
            textSize = 11f
            setTextColor(0xFF8BFFB0.toInt())
        })
        row.addView(middle, LinearLayout.LayoutParams(0, -2, 1f))

        val right = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            gravity = Gravity.END
        }
        right.addView(TextView(this).apply {
            text = "↓ " + formatBytes(d.rx)
            textSize = 13f
            setTextColor(Color.WHITE)
        })
        right.addView(TextView(this).apply {
            text = "↑ " + formatBytes(d.tx)
            textSize = 13f
            setTextColor(Color.WHITE)
        })
        right.addView(TextView(this).apply {
            text = sites.count { it.ip == d.ip }.toString() + " website  ›"
            textSize = 11f
            setTextColor(0xEEFFFFFF.toInt())
            setPadding(8.dp(), 5.dp(), 0, 0)
        })
        row.addView(right)

        return row.withMargins(0, 5.dp(), 0, 7.dp())
    }

    private fun websiteCard(filterIp: String?): View {
        val box = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(8.dp(), 4.dp(), 8.dp(), 4.dp())
            background = glassCard()
        }

        val filtered = if (filterIp == null) sites else sites.filter { it.ip == filterIp }
        val shown = filtered.distinctBy { it.ip + "|" + it.domain }.take(8)

        if (shown.isEmpty()) {
            box.addView(TextView(this).apply {
                text = "Chưa có dữ liệu DNS. Hãy bật DNS logging trên OpenWrt."
                textSize = 13f
                setTextColor(0xE8FFFFFF.toInt())
                setPadding(8.dp(), 12.dp(), 8.dp(), 12.dp())
            })
            return box.withMargins(0, 0, 0, 8.dp())
        }

        shown.forEachIndexed { idx, s ->
            val line = LinearLayout(this).apply {
                orientation = LinearLayout.HORIZONTAL
                gravity = Gravity.CENTER_VERTICAL
                setPadding(4.dp(), 9.dp(), 4.dp(), 9.dp())
            }
            line.addView(TextView(this).apply {
                text = "◎"
                textSize = 17f
                setTextColor(Color.WHITE)
            }, LinearLayout.LayoutParams(30.dp(), -2))
            line.addView(TextView(this).apply {
                text = s.domain
                textSize = 14f
                setTextColor(Color.WHITE)
            }, LinearLayout.LayoutParams(0, -2, 1f))
            line.addView(TextView(this).apply {
                text = s.time
                textSize = 10f
                setTextColor(0xCCFFFFFF.toInt())
            })
            box.addView(line)
            if (idx < shown.lastIndex) {
                box.addView(View(this).apply {
                    setBackgroundColor(0x44FFFFFF.toInt())
                }, LinearLayout.LayoutParams(-1, 1))
            }
        }

        return box.withMargins(0, 0, 0, 8.dp())
    }

    private fun showDevicePage(d: DeviceInfo) {
        root.removeAllViews()

        val page = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(18.dp(), 18.dp(), 18.dp(), 22.dp())
            background = pinkGradient()
        }

        val bar = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
        }
        bar.addView(TextView(this).apply {
            text = "‹"
            textSize = 40f
            setTextColor(Color.WHITE)
            setOnClickListener { showDashboard() }
        }, LinearLayout.LayoutParams(48.dp(), 60.dp()))
        bar.addView(TextView(this).apply {
            text = if (d.name.isEmpty()) "Thiết bị" else d.name
            textSize = 24f
            typeface = Typeface.DEFAULT_BOLD
            setTextColor(Color.WHITE)
        })
        page.addView(bar)

        page.addView(pill(d.ip + "  •  " + d.mac))
        page.addView(summaryForDevice(d))

        page.addView(TextView(this).apply {
            text = "Website đã truy cập"
            textSize = 22f
            typeface = Typeface.DEFAULT_BOLD
            setTextColor(Color.WHITE)
            setPadding(6.dp(), 20.dp(), 6.dp(), 8.dp())
        })
        page.addView(websiteCard(d.ip))

        page.addView(TextView(this).apply {
            text = "Domain được lấy từ DNS query của router. Với HTTPS, router thường chỉ thấy hostname/domain chứ không thấy đầy đủ URL, path hoặc nội dung trang."
            textSize = 12f
            setTextColor(0xD8FFFFFF.toInt())
            setPadding(6.dp(), 12.dp(), 6.dp(), 0)
        })

        root.addView(page, FrameLayout.LayoutParams(-1, -1))
    }

    private fun summaryForDevice(d: DeviceInfo): View {
        val row = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER
        }
        row.addView(metric("↓", "Download", formatBytes(d.rx)))
        row.addView(metric("↑", "Upload", formatBytes(d.tx)))
        row.addView(metric("#", "Connections", d.conns.toString()))
        return row
    }

    private fun showWebsitePage(filterIp: String?) {
        root.removeAllViews()

        val page = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(18.dp(), 20.dp(), 18.dp(), 22.dp())
            background = pinkGradient()
        }

        page.addView(TextView(this).apply {
            text = "Website"
            textSize = 28f
            typeface = Typeface.DEFAULT_BOLD
            setTextColor(Color.WHITE)
        })

        val ips = sites.map { it.ip }.distinct()
        val labels = mutableListOf("Tất cả thiết bị")
        labels.addAll(ips)

        val spinner = Spinner(this)
        spinner.adapter = ArrayAdapter(
            this,
            android.R.layout.simple_spinner_dropdown_item,
            labels
        )
        spinner.setSelection(if (filterIp == null) 0 else ips.indexOf(filterIp) + 1)
        spinner.onItemSelectedListener = object : AdapterView.OnItemSelectedListener {
            override fun onNothingSelected(parent: AdapterView<*>?) {}
            override fun onItemSelected(parent: AdapterView<*>?, view: View?, position: Int, id: Long) {
                val selected = if (position == 0) null else ips.getOrNull(position - 1)
                if (selected != filterIp) showWebsitePage(selected)
            }
        }
        page.addView(spinner, LinearLayout.LayoutParams(-1, 50.dp()).apply {
            topMargin = 10.dp()
            bottomMargin = 10.dp()
        })

        page.addView(websiteCard(filterIp), LinearLayout.LayoutParams(-1, 0, 1f))

        page.addView(Button(this).apply {
            text = "‹  Quay lại"
            setOnClickListener { showDashboard() }
        }, LinearLayout.LayoutParams(-1, 50.dp()))

        root.addView(page, FrameLayout.LayoutParams(-1, -1))
    }

    private fun bottomNav(): View {
        val nav = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER
            background = glassCard()
            setPadding(2.dp(), 4.dp(), 2.dp(), 4.dp())
        }

        nav.addView(navItem("⌂", "Tổng quan") { showDashboard() })
        nav.addView(navItem("◎", "Website") { showWebsitePage(null) })
        nav.addView(navItem("▥", "Thống kê") { toast("Thống kê đang cập nhật") })
        nav.addView(navItem("⚙", "Cài đặt") { showLogin() })

        return nav.withMargins(0, 12.dp(), 0, 0)
    }

    private fun navItem(icon: String, label: String, action: () -> Unit): View {
        val item = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            gravity = Gravity.CENTER
            setPadding(2.dp(), 4.dp(), 2.dp(), 4.dp())
            setOnClickListener { action() }
        }
        item.addView(TextView(this).apply {
            text = icon
            textSize = 22f
            gravity = Gravity.CENTER
            setTextColor(Color.WHITE)
        })
        item.addView(TextView(this).apply {
            text = label
            textSize = 10f
            gravity = Gravity.CENTER
            setTextColor(Color.WHITE)
        })
        return item.withWeight(1f)
    }

    private fun fetchData(initial: Boolean) {
        executor.execute {
            var conn: HttpURLConnection? = null
            try {
                val host = routerIp.removePrefix("http://").removePrefix("https://").trimEnd('/')
                val encoded = URLEncoder.encode(apiKey, "UTF-8")
                val endpoint = "http://" + host + "/cgi-bin/datbeo-traffic?key=" + encoded

                conn = (URL(endpoint).openConnection() as HttpURLConnection).apply {
                    requestMethod = "GET"
                    connectTimeout = 8000
                    readTimeout = 8000
                    useCaches = false
                    setRequestProperty("Accept", "application/json")
                    setRequestProperty("X-API-Key", apiKey)
                }

                val code = conn.responseCode
                val body = (if (code in 200..299) conn.inputStream else conn.errorStream)
                    ?.bufferedReader()?.use { it.readText() } ?: ""

                if (code !in 200..299) throw Exception("HTTP " + code)

                val json = JSONObject(body)
                if (json.optString("error").isNotBlank()) {
                    throw Exception("API: " + json.optString("error"))
                }

                val leases = json.optJSONArray("leases")
                val leaseMap = mutableMapOf<String, Pair<String, String>>()
                if (leases != null) {
                    for (i in 0 until leases.length()) {
                        val d = leases.getJSONObject(i)
                        leaseMap[d.optString("mac").lowercase()] =
                            d.optString("name", "Thiết bị") to d.optString("ip", "")
                    }
                }

                val traffic = json.optJSONArray("traffic")
                val newDevices = mutableListOf<DeviceInfo>()
                if (traffic != null) {
                    for (i in 0 until traffic.length()) {
                        val t = traffic.getJSONObject(i)
                        val mac = t.optString("mac")
                        val pair = leaseMap[mac.lowercase()]
                        newDevices.add(
                            DeviceInfo(
                                pair?.first ?: "Thiết bị",
                                pair?.second ?: "",
                                mac,
                                t.optLong("rx_bytes"),
                                t.optLong("tx_bytes"),
                                t.optLong("conns")
                            )
                        )
                    }
                }

                val webJson = json.optJSONArray("websites")
                val newSites = mutableListOf<SiteVisit>()
                if (webJson != null) {
                    for (i in 0 until webJson.length()) {
                        val w = webJson.getJSONObject(i)
                        newSites.add(
                            SiteVisit(
                                w.optString("time"),
                                w.optString("domain"),
                                w.optString("ip")
                            )
                        )
                    }
                }

                devices = newDevices
                sites = newSites
                lastUpdated = java.text.SimpleDateFormat("HH:mm:ss").format(java.util.Date())

                runOnUiThread {
                    if (connected) {
                        showDashboard()
                    }
                }
            } catch (e: Exception) {
                if (initial) {
                    runOnUiThread {
                        toast("Lỗi kết nối: " + (e.message ?: "unknown"))
                        showLogin()
                    }
                }
            } finally {
                conn?.disconnect()
            }
        }
    }

    private fun pinkGradient() = GradientDrawable(
        GradientDrawable.Orientation.TL_BR,
        intArrayOf(Color.rgb(150, 10, 160), Color.rgb(230, 20, 104))
    )

    private fun glassCard() = GradientDrawable().apply {
        setColor(0x1FFFFFFF)
        cornerRadius = 22f
        setStroke(1, 0x55FFFFFF)
    }

    private fun glassEditBackground() = GradientDrawable().apply {
        setColor(0x2BFFFFFF)
        cornerRadius = 7f
    }

    private fun outlineButton() = GradientDrawable().apply {
        setColor(0x00FFFFFF)
        cornerRadius = 5f
        setStroke(2, 0x55FFFFFF)
    }

    private fun fieldParams() = LinearLayout.LayoutParams(-1, 54.dp()).apply {
        bottomMargin = 9.dp()
    }

    private fun pill(textValue: String) = TextView(this).apply {
        text = textValue
        textSize = 15f
        gravity = Gravity.CENTER
        setTextColor(Color.WHITE)
        setPadding(12.dp(), 8.dp(), 12.dp(), 8.dp())
        background = GradientDrawable().apply {
            setColor(0x22FFFFFF)
            cornerRadius = 40f
            setStroke(1, 0x44FFFFFF)
        }
        layoutParams = LinearLayout.LayoutParams(-1, -2).apply {
            topMargin = 8.dp()
            bottomMargin = 8.dp()
        }
    }

    private fun card(view: View): View {
        if (view.background == null) view.background = glassCard()
        return view.withMargins(0, 6.dp(), 0, 8.dp())
    }

    private fun deviceIcon(name: String): String {
        val s = name.lowercase()
        return when {
            s.contains("iphone") || s.contains("android") || s.contains("phone") || s.contains("điện thoại") -> "▣"
            s.contains("laptop") || s.contains("mac") || s.contains("pc") || s.contains("máy") -> "▱"
            else -> "◉"
        }
    }

    private fun formatBytes(v: Long): String {
        var n = v.toDouble()
        val units = arrayOf("B", "KB", "MB", "GB", "TB")
        var i = 0
        while (n >= 1024 && i < units.lastIndex) {
            n /= 1024
            i++
        }
        return if (i == 0) v.toString() + " B" else String.format("%.1f %s", n, units[i])
    }

    private fun toast(s: String) {
        Toast.makeText(this, s, Toast.LENGTH_SHORT).show()
    }

    private fun Int.dp(): Int =
        (this * resources.displayMetrics.density).toInt()

    private fun View.withMargins(l: Int, t: Int, r: Int, b: Int): View {
        layoutParams = LinearLayout.LayoutParams(
            if (layoutParams?.width ?: -1 == 0) 0 else (layoutParams?.width ?: -1),
            layoutParams?.height ?: -2
        ).apply { setMargins(l, t, r, b) }
        return this
    }

    private fun View.withWeight(weight: Float): View {
        layoutParams = LinearLayout.LayoutParams(0, -2, weight)
        return this
    }

    override fun onDestroy() {
        connected = false
        handler.removeCallbacks(refreshRunnable)
        executor.shutdownNow()
        super.onDestroy()
    }
}
