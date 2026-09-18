package com.datbeo.routermonitor
import android.app.Activity
import android.os.Bundle
import android.graphics.Color
import android.view.ViewGroup
import android.widget.*
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.util.concurrent.Executors

class MainActivity:Activity(){
 private val ex=Executors.newSingleThreadExecutor()
 private lateinit var ip:EditText; private lateinit var key:EditText; private lateinit var out:TextView
 override fun onCreate(b:Bundle?){super.onCreate(b); ui()}
 private fun ui(){
  val box=LinearLayout(this).apply{orientation=LinearLayout.VERTICAL;setPadding(24,24,24,24)}
  val scroll=ScrollView(this); val c=LinearLayout(this).apply{orientation=LinearLayout.VERTICAL};scroll.addView(c)
  c.addView(TextView(this).apply{text="DatBeo Router Monitor";textSize=26f;setTextColor(Color.BLACK)})
  c.addView(TextView(this).apply{text="OpenWrt traffic via NetBird";textSize=14f})
  ip=EditText(this).apply{hint="NetBird IP, e.g. 100.x.x.x";setSingleLine(true)}
  key=EditText(this).apply{hint="OpenWrt API key";setSingleLine(true)}
  c.addView(ip);c.addView(key)
  c.addView(Button(this).apply{text="Connect / Refresh";setOnClickListener{load()}})
  out=TextView(this).apply{text="Not connected";textSize=15f;setPadding(0,20,0,0)}
  c.addView(out);box.addView(scroll,ViewGroup.LayoutParams(-1,-1));setContentView(box)
 }
 private fun load(){
  val h=ip.text.toString().trim();val k=key.text.toString().trim()
  if(h.isEmpty()||k.isEmpty()){out.text="Enter NetBird IP and API key";return}
  out.text="Connecting..."
  ex.execute{try{
   val base=if(h.startsWith("http"))h else "http://$h"
   val q=(URL("$base/cgi-bin/datbeo-traffic").openConnection() as HttpURLConnection).apply{
    connectTimeout=5000;readTimeout=7000;setRequestProperty("X-API-Key",k)}
   val code=q.responseCode;val body=(if(code in 200..299)q.inputStream else q.errorStream).bufferedReader().use{it.readText()}
   if(code !in 200..299)throw Exception("HTTP $code")
   val j=JSONObject(body);val s=StringBuilder()
   s.append(j.optString("hostname")).append("\nNetBird: ").append(j.optString("netbird_ip")).append("\n\n")
   val a=j.optJSONArray("traffic");if(a!=null)for(i in 0 until a.length()){val o=a.getJSONObject(i);s.append(o.optString("mac")).append("  down ").append(o.optLong("rx_bytes")).append("  up ").append(o.optLong("tx_bytes")).append("\n")}
   val l=j.optJSONArray("leases");s.append("\nDEVICES\n");if(l!=null)for(i in 0 until l.length()){val o=l.getJSONObject(i);s.append(o.optString("name")).append("  ").append(o.optString("ip")).append("  ").append(o.optString("mac")).append("\n")}
   runOnUiThread{out.text=s.toString()}
  }catch(err:Exception){runOnUiThread{out.text="Error: "+err.message}}}
 }
 override fun onDestroy(){ex.shutdownNow();super.onDestroy()}
}