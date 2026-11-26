package com.bioaccess.mobile;

import android.Manifest;
import android.app.Activity;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.graphics.ImageFormat;
import android.graphics.drawable.GradientDrawable;
import android.hardware.Camera;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.util.Log;
import android.view.Gravity;
import android.view.SurfaceHolder;
import android.view.SurfaceView;
import android.view.View;
import android.view.ViewGroup;
import android.view.animation.Animation;
import android.view.animation.LinearInterpolator;
import android.view.animation.TranslateAnimation;
import android.app.AlertDialog;
import android.content.DialogInterface;
import android.widget.Button;
import android.widget.EditText;
import android.widget.FrameLayout;
import android.widget.LinearLayout;
import android.widget.TextView;

import com.google.zxing.BarcodeFormat;
import com.google.zxing.BinaryBitmap;
import com.google.zxing.DecodeHintType;
import com.google.zxing.MultiFormatReader;
import com.google.zxing.PlanarYUVLuminanceSource;
import com.google.zxing.Result;
import com.google.zxing.common.HybridBinarizer;

import org.json.JSONObject;

import java.util.ArrayList;
import java.util.EnumMap;
import java.util.List;
import java.util.Map;

@SuppressWarnings("deprecation")
public class QrScanActivity extends Activity implements SurfaceHolder.Callback, Camera.PreviewCallback {

    private static final String TAG = "BioAccessQR";
    private static final int REQ_CAM = 42;
    private static final long TIMEOUT_MS = 60000;

    public static final String EXTRA_RESULT = "qr_result";

    private SurfaceView surfaceView;
    private Camera camera;
    private volatile boolean decoding = false;
    private volatile boolean finished = false;
    private volatile boolean previewing = false;
    private boolean torchOn = false;
    private TextView hint;
    private TextView title;
    private TextView status;
    private View scanLine;
    private View frame;
    private final Handler ui = new Handler(Looper.getMainLooper());
    private final Runnable timeoutRunnable = () -> finishWithError("timeout");

    private final int NEON_CYAN = 0xFF22D3FF;
    private final int NEON_MAGENTA = 0xFFFF2D95;
    private final int NEON_RED = 0xFFFF3B5C;
    private final int BG = 0xFF020610;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        FrameLayout root = new FrameLayout(this);
        root.setBackgroundColor(BG);

        surfaceView = new SurfaceView(this);
        surfaceView.getHolder().addCallback(this);
        root.addView(surfaceView, new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));

        View veil = new View(this);
        veil.setBackgroundColor(0x44000000);
        root.addView(veil, new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));

        frame = new View(this);
        GradientDrawable gd = new GradientDrawable();
        gd.setColor(0x11000000);
        gd.setStroke(dp(3), NEON_CYAN);
        gd.setCornerRadius(dp(6));
        frame.setBackground(gd);
        FrameLayout.LayoutParams fp = new FrameLayout.LayoutParams(dp(280), dp(280));
        fp.gravity = Gravity.CENTER;
        root.addView(frame, fp);

        addCorner(root, Gravity.CENTER, -dp(140), -dp(140));
        addCorner(root, Gravity.CENTER, dp(140) - dp(18), -dp(140));
        addCorner(root, Gravity.CENTER, -dp(140), dp(140) - dp(18));
        addCorner(root, Gravity.CENTER, dp(140) - dp(18), dp(140) - dp(18));

        scanLine = new View(this);
        GradientDrawable sld = new GradientDrawable();
        sld.setColor(NEON_MAGENTA);
        sld.setCornerRadius(dp(2));
        scanLine.setBackground(sld);
        FrameLayout.LayoutParams slp = new FrameLayout.LayoutParams(dp(250), dp(4));
        slp.gravity = Gravity.CENTER_HORIZONTAL | Gravity.TOP;
        slp.topMargin = (getResources().getDisplayMetrics().heightPixels / 2) - dp(130);
        root.addView(scanLine, slp);

        title = new TextView(this);
        title.setText(">> BIOACCESS QR SCANNER <<");
        title.setTextColor(NEON_CYAN);
        title.setTextSize(16f);
        title.setGravity(Gravity.CENTER);
        title.setShadowLayer(12f, 0, 0, NEON_CYAN);
        FrameLayout.LayoutParams tp = new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        tp.gravity = Gravity.TOP | Gravity.CENTER_HORIZONTAL;
        tp.topMargin = dp(24);
        root.addView(title, tp);

        TextView sub = new TextView(this);
        sub.setText("// ALINEA EL CODIGO EN EL MARCO  //  BUENA LUZ");
        sub.setTextColor(NEON_MAGENTA);
        sub.setTextSize(11f);
        sub.setGravity(Gravity.CENTER);
        FrameLayout.LayoutParams sp = new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        sp.gravity = Gravity.TOP | Gravity.CENTER_HORIZONTAL;
        sp.topMargin = dp(50);
        root.addView(sub, sp);

        hint = new TextView(this);
        hint.setText("ESPERANDO CODIGO...");
        hint.setTextColor(NEON_CYAN);
        hint.setTextSize(13f);
        hint.setGravity(Gravity.CENTER);
        FrameLayout.LayoutParams hp = new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        hp.gravity = Gravity.BOTTOM | Gravity.CENTER_HORIZONTAL;
        hp.bottomMargin = dp(90);
        root.addView(hint, hp);

        status = new TextView(this);
        status.setText("CAMARA ACTIVA // DECODIFICANDO");
        status.setTextColor(0xFF3A6B7C);
        status.setTextSize(10f);
        status.setGravity(Gravity.CENTER);
        FrameLayout.LayoutParams stp = new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        stp.gravity = Gravity.BOTTOM | Gravity.CENTER_HORIZONTAL;
        stp.bottomMargin = dp(70);
        root.addView(status, stp);

        Button torch = new Button(this);
        torch.setText("LUZ");
        torch.setTextColor(0xFF020610);
        torch.setTextSize(11f);
        GradientDrawable tbg = new GradientDrawable();
        tbg.setColor(0xFFFFD33D);
        tbg.setCornerRadius(dp(4));
        torch.setBackground(tbg);
        torch.setOnClickListener(v -> toggleTorch());
        FrameLayout.LayoutParams tlp = new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        tlp.gravity = Gravity.TOP | Gravity.START;
        tlp.topMargin = dp(20);
        tlp.leftMargin = dp(20);
        root.addView(torch, tlp);

        Button paste = new Button(this);
        paste.setText("PEGAR");
        paste.setTextColor(0xFF020610);
        paste.setTextSize(11f);
        GradientDrawable pbg = new GradientDrawable();
        pbg.setColor(0xFF2DFFB0);
        pbg.setCornerRadius(dp(4));
        paste.setBackground(pbg);
        paste.setOnClickListener(v -> showPasteDialog());
        FrameLayout.LayoutParams plp = new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        plp.gravity = Gravity.BOTTOM | Gravity.START;
        plp.bottomMargin = dp(20);
        plp.leftMargin = dp(20);
        root.addView(paste, plp);

        Button cancel = new Button(this);
        cancel.setText("ABORTAR");
        cancel.setTextColor(0xFF020610);
        cancel.setTextSize(12f);
        GradientDrawable cbg = new GradientDrawable();
        cbg.setColor(NEON_RED);
        cbg.setCornerRadius(dp(4));
        cancel.setBackground(cbg);
        cancel.setOnClickListener(v -> finishWithError("cancelado"));
        FrameLayout.LayoutParams cp = new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        cp.gravity = Gravity.TOP | Gravity.END;
        cp.topMargin = dp(20);
        cp.rightMargin = dp(20);
        root.addView(cancel, cp);

        setContentView(root);

        if (checkSelfPermission(Manifest.permission.CAMERA) != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(new String[]{Manifest.permission.CAMERA}, REQ_CAM);
        } else {
            startCamera();
        }
        ui.postDelayed(timeoutRunnable, TIMEOUT_MS);
        startScanAnimation();
    }

    private void addCorner(FrameLayout root, int gravity, int xOff, int yOff) {
        View c = new View(this);
        c.setBackgroundColor(NEON_MAGENTA);
        FrameLayout.LayoutParams lp = new FrameLayout.LayoutParams(dp(18), dp(18));
        lp.gravity = gravity;
        lp.leftMargin = xOff;
        lp.topMargin = yOff;
        root.addView(c, lp);
    }

    private int dp(int v) {
        return Math.round(v * getResources().getDisplayMetrics().density);
    }

    private void startScanAnimation() {
        final int travel = dp(250);
        TranslateAnimation anim = new TranslateAnimation(0, 0, 0, travel);
        anim.setDuration(1100);
        anim.setRepeatCount(Animation.INFINITE);
        anim.setRepeatMode(Animation.REVERSE);
        anim.setInterpolator(new LinearInterpolator());
        scanLine.startAnimation(anim);
    }

    @Override
    public void onRequestPermissionsResult(int requestCode, String[] permissions, int[] grantResults) {
        if (requestCode == REQ_CAM) {
            if (grantResults.length > 0 && grantResults[0] == PackageManager.PERMISSION_GRANTED) {
                startCamera();
            } else {
                finishWithError("permiso_camara_denegado");
            }
        }
    }

    private void startCamera() {
        try {
            camera = Camera.open();
            if (camera == null) {
                finishWithError("camara_no_disponible");
                return;
            }
            Camera.Parameters p = camera.getParameters();
            p.setPreviewFormat(ImageFormat.NV21);
            Camera.Size best = choosePreviewSize(p.getSupportedPreviewSizes());
            if (best != null) p.setPreviewSize(best.width, best.height);
            Log.d(TAG, "preview size = " + (best == null ? "null" : best.width + "x" + best.height));

            List<String> fm = p.getSupportedFocusModes();
            if (fm != null) {
                if (fm.contains(Camera.Parameters.FOCUS_MODE_CONTINUOUS_PICTURE)) {
                    p.setFocusMode(Camera.Parameters.FOCUS_MODE_CONTINUOUS_PICTURE);
                } else if (fm.contains(Camera.Parameters.FOCUS_MODE_MACRO)) {
                    p.setFocusMode(Camera.Parameters.FOCUS_MODE_MACRO);
                } else if (fm.contains(Camera.Parameters.FOCUS_MODE_AUTO)) {
                    p.setFocusMode(Camera.Parameters.FOCUS_MODE_AUTO);
                }
            }
            // autofocus area al centro
            try {
                if (p.getMaxNumFocusAreas() > 0) {
                    List<Camera.Area> areas = new ArrayList<Camera.Area>();
                    areas.add(new Camera.Area(new android.graphics.Rect(-300, -300, 300, 300), 1000));
                    p.setFocusAreas(areas);
                }
            } catch (Exception ignored) {}
            camera.setParameters(p);
            camera.setDisplayOrientation(90);

            SurfaceHolder h = surfaceView.getHolder();
            if (h.getSurface() != null && h.getSurface().isValid()) {
                try {
                    camera.setPreviewDisplay(h);
                    camera.setPreviewCallback(this);
                    camera.startPreview();
                    previewing = true;
                    Log.d(TAG, "preview started (immediate)");
                } catch (Exception e2) {
                    Log.e(TAG, "preview start failed", e2);
                }
            }
            // retry si la superficie no estaba lista
            ui.postDelayed(new Runnable() {
                @Override public void run() {
                    if (finished || camera == null || previewing) return;
                    SurfaceHolder hh = surfaceView.getHolder();
                    if (hh.getSurface() != null && hh.getSurface().isValid()) {
                        try {
                            camera.setPreviewDisplay(hh);
                            camera.setPreviewCallback(QrScanActivity.this);
                            camera.startPreview();
                            previewing = true;
                            Log.d(TAG, "preview started (delayed)");
                        } catch (Exception e2) {
                            Log.e(TAG, "delayed preview failed", e2);
                        }
                    } else {
                        ui.postDelayed(this, 300);
                    }
                }
            }, 300);

            ui.postDelayed(new Runnable() {
                @Override public void run() {
                    if (finished || camera == null) return;
                    try { camera.autoFocus(null); } catch (Exception ignored) {}
                    ui.postDelayed(this, 2000);
                }
            }, 1200);
        } catch (Exception e) {
            Log.e(TAG, "open camera failed", e);
            finishWithError("camara_no_disponible");
        }
    }

    private Camera.Size choosePreviewSize(List<Camera.Size> sizes) {
        if (sizes == null || sizes.isEmpty()) return null;
        Camera.Size best = null;
        int bestScore = Integer.MAX_VALUE;
        for (Camera.Size s : sizes) {
            int score = Math.abs(s.width - 1280) + Math.abs(s.height - 720);
            if (best == null || score < bestScore) { best = s; bestScore = score; }
        }
        return best;
    }

    private void toggleTorch() {
        if (camera == null) return;
        try {
            Camera.Parameters p = camera.getParameters();
            List<String> flash = p.getSupportedFlashModes();
            if (flash == null || !flash.contains(Camera.Parameters.FLASH_MODE_TORCH)) {
                hint.setText("SIN LINTERNA");
                return;
            }
            torchOn = !torchOn;
            p.setFlashMode(torchOn ? Camera.Parameters.FLASH_MODE_TORCH : Camera.Parameters.FLASH_MODE_OFF);
            camera.setParameters(p);
            hint.setText(torchOn ? "LUZ ACTIVADA" : "ESPERANDO CODIGO...");
        } catch (Exception e) {
            Log.e(TAG, "torch failed", e);
        }
    }

    @Override
    public void surfaceCreated(SurfaceHolder holder) {
        if (camera == null) return;
        if (previewing) return;
        try {
            camera.setPreviewDisplay(holder);
            camera.setPreviewCallback(this);
            camera.startPreview();
            previewing = true;
            Log.d(TAG, "preview started (surfaceCreated)");
        } catch (Exception e) {
            Log.e(TAG, "preview failed", e);
            finishWithError("preview_fallido");
        }
    }

    @Override
    public void surfaceChanged(SurfaceHolder holder, int format, int w, int h) {}

    @Override
    public void surfaceDestroyed(SurfaceHolder holder) {
        stopCamera();
    }

    private void stopCamera() {
        try {
            if (camera != null) {
                camera.setPreviewCallback(null);
                try { camera.stopPreview(); } catch (Exception ignored) {}
                camera.release();
            }
        } catch (Exception ignored) {}
        camera = null;
        previewing = false;
    }

    @Override
    public void onPreviewFrame(byte[] data, Camera cam) {
        if (finished) return;
        if (decoding) return;
        decoding = true;
        final Camera.Parameters params = cam.getParameters();
        final Camera.Size size = params.getPreviewSize();
        final int w = size.width;
        final int h = size.height;
        final byte[] frameData = data;
        new Thread(() -> {
            boolean ok = false;
            try {
                // 1) recorte central seguro
                int cropW = (w * 7 / 10);
                int cropH = (h * 7 / 10);
                if (cropW % 2 != 0) cropW--;
                if (cropH % 2 != 0) cropH--;
                int left = (w - cropW) / 2;
                int top = (h - cropH) / 2;
                if (left < 0) left = 0;
                if (top < 0) top = 0;
                if (left + cropW > w) cropW = w - left;
                if (top + cropH > h) cropH = h - top;
                if (cropW > 0 && cropH > 0) {
                    PlanarYUVLuminanceSource source =
                            new PlanarYUVLuminanceSource(frameData, w, h, left, top, cropW, cropH, false);
                    if (tryDecode(source)) { ok = true; }
                    if (!ok) { if (tryDecode(source.rotateCounterClockwise())) { ok = true; } }
                }
                // 2) frame completo (siempre como fallback)
                if (!ok) {
                    PlanarYUVLuminanceSource full =
                            new PlanarYUVLuminanceSource(frameData, w, h, 0, 0, w, h, false);
                    if (tryDecode(full)) { ok = true; }
                    if (!ok) { tryDecode(full.rotateCounterClockwise()); }
                }
            } catch (Exception e) {
                Log.e(TAG, "decode error", e);
            } finally {
                decoding = false;
            }
        }).start();
    }

    private boolean tryDecode(com.google.zxing.LuminanceSource src) {
        com.google.zxing.Binarizer[] bins = new com.google.zxing.Binarizer[] {
            new HybridBinarizer(src),
            new com.google.zxing.common.GlobalHistogramBinarizer(src)
        };
        for (com.google.zxing.Binarizer bin : bins) {
            try {
                BinaryBitmap bitmap = new BinaryBitmap(bin);
                MultiFormatReader reader = new MultiFormatReader();
                Map<DecodeHintType, Object> hints = new EnumMap<>(DecodeHintType.class);
                hints.put(DecodeHintType.TRY_HARDER, Boolean.TRUE);
                hints.put(DecodeHintType.POSSIBLE_FORMATS, java.util.Arrays.asList(BarcodeFormat.QR_CODE));
                reader.setHints(hints);
                Result result = reader.decode(bitmap);
                if (result != null && result.getText() != null) {
                    String text = result.getText().trim();
                    Log.d(TAG, "DECODED: " + text);
                    finished = true;
                    ui.removeCallbacks(timeoutRunnable);
                    if (scanLine != null) scanLine.clearAnimation();
                    Intent i = new Intent();
                    i.putExtra(EXTRA_RESULT, text);
                    runOnUiThread(() -> { setResult(RESULT_OK, i); finish(); });
                    return true;
                }
            } catch (Exception ignored) {
                // no code in this frame with this binarizer
            }
        }
        return false;
    }

    private void showPasteDialog() {
        final EditText et = new EditText(this);
        et.setHint("bioaccess://pair?...");
        et.setTextColor(0xFFFFFFFF);
        LinearLayout box = new LinearLayout(this);
        box.setOrientation(LinearLayout.VERTICAL);
        box.setPadding(dp(20), dp(10), dp(20), dp(10));
        box.addView(et);
        new AlertDialog.Builder(this)
            .setTitle("PEGAR PAYLOAD DEL QR")
            .setView(box)
            .setPositiveButton("OK", new DialogInterface.OnClickListener() {
                @Override public void onClick(DialogInterface d, int w) {
                    String t = et.getText().toString().trim();
                    if (t.isEmpty()) return;
                    finished = true;
                    ui.removeCallbacks(timeoutRunnable);
                    if (scanLine != null) scanLine.clearAnimation();
                    Intent i = new Intent();
                    i.putExtra(EXTRA_RESULT, t);
                    setResult(RESULT_OK, i);
                    finish();
                }
            })
            .setNegativeButton("CANCELAR", null)
            .show();
    }

    private void finishWithError(String reason) {
        if (finished) return;
        finished = true;
        ui.removeCallbacks(timeoutRunnable);
        if (scanLine != null) scanLine.clearAnimation();
        Intent i = new Intent();
        try {
            JSONObject o = new JSONObject();
            o.put("ok", false);
            o.put("error", reason);
            i.putExtra(EXTRA_RESULT, o.toString());
        } catch (Exception ignored) {
            i.putExtra(EXTRA_RESULT, "{\"ok\":false,\"error\":\"" + reason + "\"}");
        }
        setResult(RESULT_CANCELED, i);
        finish();
    }

    @Override
    protected void onDestroy() {
        ui.removeCallbacks(timeoutRunnable);
        if (scanLine != null) scanLine.clearAnimation();
        stopCamera();
        super.onDestroy();
    }

    @Override
    public void onBackPressed() {
        finishWithError("cancelado");
    }
}
