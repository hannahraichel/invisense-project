package com.invisense.app.ui.scan;

import android.content.Intent;
import android.os.Bundle;
import android.view.MenuItem;
import android.view.View;
import android.widget.TextView;
import android.widget.Toast;

import androidx.appcompat.app.AppCompatActivity;
import androidx.appcompat.widget.Toolbar;
import androidx.cardview.widget.CardView;

import com.google.zxing.ResultPoint;
import com.journeyapps.barcodescanner.BarcodeCallback;
import com.journeyapps.barcodescanner.BarcodeResult;
import com.journeyapps.barcodescanner.DecoratedBarcodeView;
import com.invisense.app.R;
import com.invisense.app.api.ApiClient;
import com.invisense.app.model.QrScanRequest;
import com.invisense.app.model.QrScanResponse;
import com.invisense.app.ui.login.LoginActivity;

import java.util.List;

import retrofit2.Call;
import retrofit2.Callback;
import retrofit2.Response;

public class ScanActivity extends AppCompatActivity {

    private DecoratedBarcodeView barcodeView;
    private CardView cardResult;
    private TextView tvResultMsg, tvResultStatus;
    private View btnScanNext, btnBackDashboard;
    private boolean isProcessing = false;

    private final BarcodeCallback callback = new BarcodeCallback() {
        @Override
        public void barcodeResult(BarcodeResult result) {
            if (result == null || result.getText() == null || isProcessing) return;
            isProcessing = true;
            barcodeView.pause();
            verifyQr(result.getText());
        }

        @Override
        public void possibleResultPoints(List<ResultPoint> resultPoints) {}
    };

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_scan);

        Toolbar toolbar = findViewById(R.id.toolbar);
        setSupportActionBar(toolbar);
        if (getSupportActionBar() != null) {
            getSupportActionBar().setDisplayHomeAsUpEnabled(true);
            getSupportActionBar().setDisplayShowHomeEnabled(true);
        }
        toolbar.setNavigationOnClickListener(v -> finish());

        barcodeView      = findViewById(R.id.barcodeScannerView);
        cardResult       = findViewById(R.id.cardResult);
        tvResultMsg      = findViewById(R.id.tvResultMsg);
        tvResultStatus   = findViewById(R.id.tvResultStatus);
        btnScanNext      = findViewById(R.id.btnScanNext);
        btnBackDashboard = findViewById(R.id.btnBackDashboard);

        btnScanNext.setOnClickListener(v -> resumeScanning());
        btnBackDashboard.setOnClickListener(v -> finish());

        barcodeView.decodeContinuous(callback);
    }

    private void resumeScanning() {
        cardResult.setVisibility(View.GONE);
        isProcessing = false;
        barcodeView.resume();
    }

    @Override
    protected void onResume() {
        super.onResume();
        if (!isProcessing) {
            barcodeView.resume();
        }
    }

    @Override
    protected void onPause() {
        super.onPause();
        barcodeView.pause();
    }

    @Override
    public boolean onOptionsItemSelected(MenuItem item) {
        if (item.getItemId() == android.R.id.home) {
            finish();
            return true;
        }
        return super.onOptionsItemSelected(item);
    }

    private void verifyQr(String qrContent) {
        QrScanRequest req = new QrScanRequest(qrContent);
        ApiClient.getApi(this).verifyQr(req).enqueue(new Callback<QrScanResponse>() {
            @Override
            public void onResponse(Call<QrScanResponse> call, Response<QrScanResponse> response) {
                if (!response.isSuccessful() || response.body() == null) {
                    if (response.code() == 401) { handleUnauth(); return; }
                    showResult("error", "Server error. Try scanning again.");
                    return;
                }
                QrScanResponse body = response.body();
                showResult(body.status, body.message);
            }

            @Override
            public void onFailure(Call<QrScanResponse> call, Throwable t) {
                showResult("error", "Network error: " + t.getMessage());
            }
        });
    }

    private void showResult(String status, String msg) {
        cardResult.setVisibility(View.VISIBLE);
        tvResultMsg.setText(msg);

        if ("success".equalsIgnoreCase(status)) {
            tvResultStatus.setText("VERIFIED PRESENT");
            tvResultStatus.setTextColor(getResources().getColor(R.color.success));
        } else if ("warning".equalsIgnoreCase(status)) {
            tvResultStatus.setText("ATTENTION REQUIRED");
            tvResultStatus.setTextColor(getResources().getColor(R.color.warning));
        } else {
            tvResultStatus.setText("VERIFICATION FAILED");
            tvResultStatus.setTextColor(getResources().getColor(R.color.danger));
        }
    }

    private void handleUnauth() {
        ApiClient.clearToken(this);
        Toast.makeText(this, "Session expired. Please log in again.", Toast.LENGTH_SHORT).show();
        startActivity(new Intent(this, LoginActivity.class));
        finish();
    }
}
