package com.bioaccess.mobile;

import android.annotation.SuppressLint;
import android.app.Activity;
import android.content.Context;
import android.content.DialogInterface;
import android.content.Intent;
import android.graphics.Color;
import android.hardware.biometrics.BiometricManager;
import android.hardware.biometrics.BiometricPrompt;
import android.os.Build;
import android.os.Bundle;
import android.os.CancellationSignal;
import android.os.Handler;
import android.os.Looper;
import android.os.VibrationEffect;
import android.os.Vibrator;
import android.net.Uri;
import android.view.View;
import android.view.Window;
import android.view.WindowManager;
import android.webkit.JavascriptInterface;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceResponse;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;

import org.json.JSONObject;

import java.io.ByteArrayInputStream;
import java.io.IOException;
import java.net.DatagramPacket;
import java.net.DatagramSocket;
import java.net.InetAddress;
import java.net.InterfaceAddress;
import java.net.NetworkInterface;
import java.net.SocketTimeoutException;
import java.util.ArrayList;
import java.util.Enumeration;
import java.util.List;

/**
 * BioAccess Mobile — contenedor nativo de la interfaz (assets/mobile).
 *
 * Puente JS  <->  Android:
 *   BioAndroid.hasBiometric()      -> true si hay lector de huellas
 *   BioAndroid.authenticate()      -> dispara el lector real; responde por
 *                                     window.onBiometricResult(ok, mensaje)
 *   BioAndroid.vibrate(pattern)    -> vibración háptica
 *   BioAndroid.discover()          -> UDP broadcast, devuelve JSON (bloqueante)
 *   BioAndroid.discoverAsync()     -> idem, responde por window.onDiscoverResult(json)
 */
@SuppressWarnings("deprecation")
public class MainActivity extends Activity {

    private static final int DISCOVERY_PORT = 8089;
    private static final String DISCOVERY_MAGIC = "BIOACCESS_DISCOVER";
    private static final int REQ_QR = 9001;

    private WebView web;
    private final Handler ui = new Handler(Looper.getMainLooper());

    @SuppressLint({"SetJavaScriptEnabled", "AddJavascriptInterface"})
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        // pantalla completa "terminal"
        requestWindowFeature(Window.FEATURE_NO_TITLE);
        getWindow().setStatusBarColor(Color.parseColor("#01040a"));
        getWindow().setNavigationBarColor(Color.parseColor("#01040a"));
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);

        web = new WebView(this);
        web.setBackgroundColor(Color.parseColor("#01040a"));
        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setAllowFileAccess(true);
        s.setAllowContentAccess(true);
        s.setAllowFileAccessFromFileURLs(true);
        s.setAllowUniversalAccessFromFileURLs(true);
        s.setMediaPlaybackRequiresUserGesture(false);
        s.setCacheMode(WebSettings.LOAD_DEFAULT);
        s.setMixedContentMode(WebSettings.MIXED_CONTENT_ALWAYS_ALLOW);
        s.setUseWideViewPort(true);
        s.setLoadWithOverviewMode(false);
        s.setSupportZoom(false);
        s.setBuiltInZoomControls(false);

        web.setWebViewClient(new WebViewClient() {
            @Override
            public WebResourceResponse shouldInterceptRequest(WebView view, WebResourceRequest request) {
                Uri u = request.getUrl();
                // Origen propio: https://bioaccess.local/...  ->  assets/mobile/...
                if (u != null && "bioaccess.local".equals(u.getHost())) {
                    String path = u.getPath();
                    if (path == null || path.isEmpty() || "/".equals(path)) path = "/index.html";
                    try {
                        String mime = mimeOf(path);
                        return new WebResourceResponse(mime, "utf-8",
                                getAssets().open("mobile" + path));
                    } catch (IOException e) {
                        String msg = "ASSET ERROR: " + e + " | path=" + path;
                        return new WebResourceResponse("text/plain", "utf-8", 404, "Not Found",
                                null, new ByteArrayInputStream(msg.getBytes(java.nio.charset.StandardCharsets.UTF_8)));
                    }
                }
                return super.shouldInterceptRequest(view, request);
            }
        });
        web.addJavascriptInterface(new Bridge(), "BioAndroid");
        try {
            WebView.setWebContentsDebuggingEnabled(true);
        } catch (Throwable ignored) {
        }
        setContentView(web);
        web.loadUrl("https://bioaccess.local/index.html");
        handleDeepLink(getIntent());
    }

    @Override
    public void onBackPressed() {
        if (web != null && web.canGoBack()) {
            web.goBack();
        } else {
            super.onBackPressed();
        }
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode == REQ_QR) {
            String res = null;
            if (data != null) res = data.getStringExtra(QrScanActivity.EXTRA_RESULT);
            if (res == null) res = "{\"ok\":false,\"error\":\"cancelado\"}";
            final String payload = res;
            // si el resultado es texto plano (no JSON), envolverlo
            String json = payload.trim().startsWith("{") ? payload
                    : "{\"ok\":true,\"payload\":\"" + payload.replace("\\","\\\\").replace("\"","\\\"") + "\"}";
            ui.post(() -> js("window.onQrResult&&window.onQrResult(" + quote(json) + ")"));
        }
    }

    @Override
    protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        handleDeepLink(intent);
    }

    private void handleDeepLink(Intent intent) {
        try {
            if (intent == null || intent.getData() == null) return;
            Uri u = intent.getData();
            if ("bioaccess".equals(u.getScheme())) {
                String uri = u.toString();
                ui.post(() -> js("window.onPairUri&&window.onPairUri(" + quote(uri) + ")"));
            }
        } catch (Throwable ignored) {
        }
    }

    @Override
    protected void onDestroy() {
        try {
            if (web != null) {
                web.loadUrl("about:blank");
                web.destroy();
            }
        } catch (Throwable ignored) {
        }
        super.onDestroy();
    }

    // ------------------------------------------------------------------
    //  Puente JavaScript
    // ------------------------------------------------------------------
    public class Bridge {

        @JavascriptInterface
        public String platform() {
            return "android";
        }

        @JavascriptInterface
        public String deviceName() {
            return (Build.MANUFACTURER + " " + Build.MODEL).trim();
        }

        /** ¿hay lector biométrico disponible y configurado? */
        @JavascriptInterface
        public boolean hasBiometric() {
            try {
                BiometricManager bm = (BiometricManager) getSystemService(Context.BIOMETRIC_SERVICE);
                if (bm != null) {
                    return bm.canAuthenticate() == BiometricManager.BIOMETRIC_SUCCESS;
                }
                return getPackageManager().hasSystemFeature(android.content.pm.PackageManager.FEATURE_FINGERPRINT);
            } catch (Throwable t) {
                return false;
            }
        }

        /** Lanza el lector biométrico del teléfono. */
        @SuppressLint("MissingPermission")
        @JavascriptInterface
        public void authenticate() {
            ui.post(() -> {
                try {
                    BiometricPrompt bp = new BiometricPrompt.Builder(MainActivity.this)
                            .setTitle("BioAccess")
                            .setSubtitle("Verificación biométrica")
                            .setDescription("Coloca tu huella para autorizar el acceso")
                            .setNegativeButton("Cancelar", getMainExecutor(),
                                    (dialog, which) -> reply(false, "cancelado"))
                            .build();
                    CancellationSignal cancel = new CancellationSignal();
                    bp.authenticate(cancel, getMainExecutor(),
                            new BiometricPrompt.AuthenticationCallback() {
                                @Override
                                public void onAuthenticationSucceeded(BiometricPrompt.AuthenticationResult result) {
                                    reply(true, "");
                                }

                                @Override
                                public void onAuthenticationFailed() {
                                    reply(false, "no_reconocida");
                                }

                                @Override
                                public void onAuthenticationError(int errorCode, CharSequence errString) {
                                    reply(false, String.valueOf(errString));
                                }
                            });
                } catch (Throwable t) {
                    reply(false, "error_sensor");
                }
            });
        }

        @JavascriptInterface
        public void vibrate(String pattern) {
            try {
                Vibrator v = (Vibrator) getSystemService(Context.VIBRATOR_SERVICE);
                if (v == null || !v.hasVibrator()) return;
                long[] pat = parsePattern(pattern);
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                    v.vibrate(VibrationEffect.createWaveform(pat, -1));
                } else {
                    v.vibrate(pat, -1);
                }
            } catch (Throwable ignored) {
            }
        }

        /** Búsqueda UDP bloqueante (usada sólo si el JS antiguo la invoca). */
        @JavascriptInterface
        public String discover() {
            return discoverBlocking();
        }

        /** Búsqueda UDP en segundo plano -> window.onDiscoverResult(json) */
        @JavascriptInterface
        public void discoverAsync() {
            new Thread(() -> {
                final String json = discoverBlocking();
                ui.post(() -> js("window.onDiscoverResult&&window.onDiscoverResult(" + quote(json) + ")"));
            }).start();
        }

        @JavascriptInterface
        public String appVersion() {
            return "2.0.1";
        }

        /** ¿El celular está conectado al PC por cable USB? */
        @JavascriptInterface
        public boolean usbConnected() {
            try {
                android.content.IntentFilter f = new android.content.IntentFilter(android.content.Intent.ACTION_BATTERY_CHANGED);
                android.content.Intent st = registerReceiver(null, f);
                if (st == null) return false;
                int plugged = st.getIntExtra(android.os.BatteryManager.EXTRA_PLUGGED, -1);
                return plugged == android.os.BatteryManager.BATTERY_PLUGGED_USB;
            } catch (Throwable t) {
                return false;
            }
        }

        /** GET HTTP nativo (bypass del WebView: sin mixed-content/CORS). */
        @JavascriptInterface
        public String httpGet(String url) {
            java.net.HttpURLConnection c = null;
            try {
                java.net.URL u = new java.net.URL(url);
                c = (java.net.HttpURLConnection) u.openConnection();
                c.setRequestMethod("GET");
                c.setConnectTimeout(8000);
                c.setReadTimeout(8000);
                c.setRequestProperty("Bypass-Tunnel-Reminder", "true");
                c.setUseCaches(false);
                int code = c.getResponseCode();
                java.io.InputStream is = (code >= 200 && code < 400) ? c.getInputStream() : c.getErrorStream();
                if (is == null) is = new java.io.ByteArrayInputStream(new byte[0]);
                java.io.BufferedReader br = new java.io.BufferedReader(new java.io.InputStreamReader(is, "UTF-8"));
                StringBuilder sb = new StringBuilder();
                String line;
                while ((line = br.readLine()) != null) sb.append(line);
                br.close();
                if (code < 200 || code >= 400) {
                    try { org.json.JSONObject _o = new org.json.JSONObject(); _o.put("ok", false); _o.put("reason", "http_" + code); _o.put("body", sb.toString()); return _o.toString(); } catch (Throwable _ig) { return "{\"ok\":false,\"reason\":\"http_error\"}"; }
                }
                return sb.toString();
            } catch (Throwable t) {
                try {
                    org.json.JSONObject o = new org.json.JSONObject();
                    o.put("ok", false);
                    o.put("reason", "net_error");
                    o.put("error", String.valueOf(t));
                    return o.toString();
                } catch (Throwable ignored) {
                    return "{\"ok\":false,\"reason\":\"net_error\"}";
                }
            } finally {
                if (c != null) try { c.disconnect(); } catch (Throwable ignored) {}
            }
        }

        @JavascriptInterface
        public String assetProbe(String path) {
            try {
                String[] list = getAssets().list("mobile");
                StringBuilder sb = new StringBuilder("list=");
                if (list != null) {
                    for (String n : list) sb.append(n).append(",");
                }
                try {
                    java.io.InputStream in = getAssets().open("mobile/" + path);
                    sb.append(" | open(").append(path).append(")=").append(in.available());
                    in.close();
                } catch (Throwable e) {
                    sb.append(" | open ERR: ").append(e);
                }
                return sb.toString();
            } catch (Throwable e) {
                return "probe ERR: " + e;
            }
        }

        /** Lanza la cámara para escanear el QR de la PC. */
        @JavascriptInterface
        public void scanQr() {
            try {
                Intent i = new Intent(MainActivity.this, QrScanActivity.class);
                startActivityForResult(i, REQ_QR);
            } catch (Throwable t) {
                ui.post(() -> js("window.onQrResult&&window.onQrResult(" + quote("{\"ok\":false,\"error\":\"" + t + "\"}") + ")"));
            }
        }

        /** Decodifica un QR desde un archivo de imagen (útil para pruebas). */
        @JavascriptInterface
        public String decodeQrBitmap(String path) {
            try {
                android.graphics.Bitmap bmp = android.graphics.BitmapFactory.decodeFile(path);
                if (bmp == null) return "{\"ok\":false,\"error\":\"bitmap_null\"}";
                com.google.zxing.RGBLuminanceSource src =
                        new com.google.zxing.RGBLuminanceSource(bmp.getWidth(), bmp.getHeight(), pixels(bmp));
                com.google.zxing.BinaryBitmap bb = new com.google.zxing.BinaryBitmap(new com.google.zxing.common.HybridBinarizer(src));
                com.google.zxing.MultiFormatReader r = new com.google.zxing.MultiFormatReader();
                com.google.zxing.Result res = r.decode(bb);
                JSONObject o = new JSONObject();
                o.put("ok", true);
                o.put("payload", res.getText());
                return o.toString();
            } catch (Throwable t) {
                return "{\"ok\":false,\"error\":\"" + t + "\"}";
            }
        }

        private int[] pixels(android.graphics.Bitmap bmp) {
            int w = bmp.getWidth(), h = bmp.getHeight();
            int[] px = new int[w * h];
            bmp.getPixels(px, 0, w, 0, 0, w, h);
            return px;
        }
    }

    // ------------------------------------------------------------------
    //  Utilidades
    // ------------------------------------------------------------------
    private void reply(boolean ok, String msg) {
        js("window.onBiometricResult&&window.onBiometricResult(" + ok + "," + quote(msg == null ? "" : msg) + ")");
    }

    private void js(final String code) {
        ui.post(() -> {
            try {
                web.evaluateJavascript(code, null);
            } catch (Throwable ignored) {
            }
        });
    }

    private static String quote(String s) {
        try {
            return JSONObject.quote(s == null ? "" : s);
        } catch (Throwable t) {
            return "\"\"";
        }
    }

    private static String mimeOf(String path) {
        String p = path.toLowerCase();
        if (p.endsWith(".html") || p.endsWith(".htm")) return "text/html";
        if (p.endsWith(".css")) return "text/css";
        if (p.endsWith(".js")) return "application/javascript";
        if (p.endsWith(".json") || p.endsWith(".webmanifest")) return "application/json";
        if (p.endsWith(".png")) return "image/png";
        if (p.endsWith(".svg")) return "image/svg+xml";
        if (p.endsWith(".ico")) return "image/x-icon";
        return "application/octet-stream";
    }

    private static long[] parsePattern(String pattern) {
        if (pattern == null || pattern.trim().isEmpty()) return new long[]{0, 40};
        String[] parts = pattern.trim().split("[,\\s]+");
        List<Long> vals = new ArrayList<>();
        for (String p : parts) {
            try {
                vals.add(Long.parseLong(p.trim()));
            } catch (Exception ignored) {
            }
        }
        if (vals.isEmpty()) return new long[]{0, 40};
        long[] out = new long[vals.size()];
        for (int i = 0; i < out.length; i++) out[i] = vals.get(i);
        return out;
    }

    /** Emite BIOACCESS_DISCOVER por broadcast y espera la respuesta de la PC. */
    private String discoverBlocking() {
        DatagramSocket socket = null;
        try {
            socket = new DatagramSocket();
            socket.setBroadcast(true);
            socket.setSoTimeout(700);
            byte[] msg = DISCOVERY_MAGIC.getBytes("UTF-8");
            for (InetAddress addr : broadcastTargets()) {
                try {
                    socket.send(new DatagramPacket(msg, msg.length, addr, DISCOVERY_PORT));
                } catch (Throwable ignored) {
                }
            }
            byte[] buf = new byte[2048];
            DatagramPacket in = new DatagramPacket(buf, buf.length);
            long deadline = System.currentTimeMillis() + 2000;
            while (System.currentTimeMillis() < deadline) {
                try {
                    socket.receive(in);
                    String txt = new String(in.getData(), 0, in.getLength(), "UTF-8").trim();
                    if (txt.startsWith("{")) {
                        JSONObject o = new JSONObject(txt);
                        JSONObject out = new JSONObject();
                        out.put("ip", o.optString("ip", ""));
                        out.put("port", o.optString("port", "8080"));
                        out.put("name", o.optString("name", "BioAccess PC"));
                        return out.toString();
                    }
                } catch (SocketTimeoutException te) {
                    // seguir esperando hasta el deadline
                }
            }
        } catch (Throwable t) {
            try {
                return new JSONObject().put("error", String.valueOf(t.getMessage())).toString();
            } catch (Throwable ignored) {
            }
        } finally {
            if (socket != null) socket.close();
        }
        return "{}";
    }

    private List<InetAddress> broadcastTargets() {
        List<InetAddress> out = new ArrayList<>();
        try {
            out.add(InetAddress.getByName("255.255.255.255"));
        } catch (Throwable ignored) {
        }
        try {
            Enumeration<NetworkInterface> ifs = NetworkInterface.getNetworkInterfaces();
            while (ifs != null && ifs.hasMoreElements()) {
                NetworkInterface ni = ifs.nextElement();
                if (!ni.isUp() || ni.isLoopback()) continue;
                for (InterfaceAddress ia : ni.getInterfaceAddresses()) {
                    InetAddress b = ia.getBroadcast();
                    if (b != null && !out.contains(b)) out.add(b);
                }
            }
        } catch (Throwable ignored) {
        }
        return out;
    }
}
