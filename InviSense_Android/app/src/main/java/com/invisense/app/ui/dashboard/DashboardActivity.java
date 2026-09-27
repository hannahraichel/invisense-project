package com.invisense.app.ui.dashboard;

import android.content.Intent;
import android.os.Bundle;
import android.os.Handler;
import android.view.Menu;
import android.view.MenuItem;
import android.view.View;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.TextView;
import android.widget.Toast;

import androidx.appcompat.app.AppCompatActivity;
import androidx.appcompat.widget.Toolbar;
import androidx.swiperefreshlayout.widget.SwipeRefreshLayout;

import com.invisense.app.R;
import com.invisense.app.api.ApiClient;
import com.invisense.app.model.DashboardResponse;
import com.invisense.app.model.SimpleResponse;
import com.invisense.app.ui.alert.AlertActivity;
import com.invisense.app.ui.login.LoginActivity;
import com.invisense.app.ui.scan.ScanActivity;

import retrofit2.Call;
import retrofit2.Callback;
import retrofit2.Response;

public class DashboardActivity extends AppCompatActivity {

    private TextView tvSubject, tvHall, tvTime, tvStatus, tvPresent, tvScanWindow;
    private Button   btnScan, btnAlert, btnRoster;
    private LinearLayout layoutExam, layoutNoExam, layoutAlertsList;
    private TextView tvNoAlerts;
    private ProgressBar  progressBar;
    private SwipeRefreshLayout swipeRefresh;

    private Handler  autoRefreshHandler = new Handler();
    private Runnable autoRefreshRunnable;
    private static final int REFRESH_INTERVAL_MS = 30_000; // 30 seconds

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_dashboard);

        Toolbar toolbar = findViewById(R.id.toolbar);
        setSupportActionBar(toolbar);

        tvSubject    = findViewById(R.id.tvSubject);
        tvHall       = findViewById(R.id.tvHall);
        tvTime       = findViewById(R.id.tvTime);
        tvStatus     = findViewById(R.id.tvStatus);
        tvPresent    = findViewById(R.id.tvPresent);
        tvScanWindow = findViewById(R.id.tvScanWindow);
        btnScan      = findViewById(R.id.btnScan);
        btnAlert     = findViewById(R.id.btnAlert);
        btnRoster    = findViewById(R.id.btnRoster);
        layoutExam       = findViewById(R.id.layoutExam);
        layoutNoExam     = findViewById(R.id.layoutNoExam);
        layoutAlertsList = findViewById(R.id.layoutAlertsList);
        tvNoAlerts       = findViewById(R.id.tvNoAlerts);
        progressBar      = findViewById(R.id.progressBar);
        swipeRefresh     = findViewById(R.id.swipeRefresh);

        btnScan.setOnClickListener(v ->
                startActivity(new Intent(this, ScanActivity.class)));
        btnAlert.setOnClickListener(v ->
                startActivity(new Intent(this, AlertActivity.class)));
        btnRoster.setOnClickListener(v ->
                startActivity(new Intent(this, RosterActivity.class)));

        swipeRefresh.setOnRefreshListener(this::loadDashboard);

        // Auto-refresh every 30 seconds
        autoRefreshRunnable = () -> {
            loadDashboard();
            autoRefreshHandler.postDelayed(autoRefreshRunnable, REFRESH_INTERVAL_MS);
        };
    }

    @Override
    protected void onResume() {
        super.onResume();
        loadDashboard();
        autoRefreshHandler.postDelayed(autoRefreshRunnable, REFRESH_INTERVAL_MS);
    }

    @Override
    protected void onPause() {
        super.onPause();
        autoRefreshHandler.removeCallbacks(autoRefreshRunnable);
    }

    private void loadDashboard() {
        progressBar.setVisibility(View.VISIBLE);

        ApiClient.getApi(this).getDashboard().enqueue(new Callback<DashboardResponse>() {
            @Override
            public void onResponse(Call<DashboardResponse> call, Response<DashboardResponse> response) {
                progressBar.setVisibility(View.GONE);
                swipeRefresh.setRefreshing(false);

                if (!response.isSuccessful() || response.body() == null) {
                    if (response.code() == 401) { handleUnauthorized(); return; }
                    showError("Could not load dashboard.");
                    return;
                }

                DashboardResponse body = response.body();
                updateUI(body);
            }

            @Override
            public void onFailure(Call<DashboardResponse> call, Throwable t) {
                progressBar.setVisibility(View.GONE);
                swipeRefresh.setRefreshing(false);
                showError("Network error. Pull down to retry.");
            }
        });
    }

    private void updateUI(DashboardResponse data) {
        if (data.hasActiveExam && data.exam != null) {
            layoutExam.setVisibility(View.VISIBLE);
            layoutNoExam.setVisibility(View.GONE);

            tvSubject.setText(data.exam.subject);
            tvHall.setText("Hall: " + data.exam.hallName);
            tvTime.setText(data.exam.startTime + " – " + data.exam.endTime);
            tvPresent.setText(data.exam.presentCount + " / " + data.exam.totalAssigned + " checked in");

            if (data.scanOpen) {
                tvStatus.setText("🟢  Scanning OPEN");
                tvScanWindow.setVisibility(View.GONE);
                btnScan.setEnabled(true);
                btnScan.setText("Scan QR Code");
            } else {
                tvStatus.setText("🔴  Scanning LOCKED");
                tvScanWindow.setText("Scanning opens 3 hours before start\n(at " + data.exam.scanOpensAt + ")");
                tvScanWindow.setVisibility(View.VISIBLE);
                btnScan.setEnabled(false);
                btnScan.setText("Scanning Not Yet Open");
            }
        } else {
            layoutExam.setVisibility(View.GONE);
            layoutNoExam.setVisibility(View.VISIBLE);
            String msg = data.message != null ? data.message
                    : "No exam assigned right now.";
            ((TextView) layoutNoExam.findViewById(R.id.tvNoExamMsg)).setText(msg);
        }

        // Render Flagged Incidents History
        if (layoutAlertsList != null) {
            layoutAlertsList.removeAllViews();
            if (data.recentAlerts != null && !data.recentAlerts.isEmpty()) {
                if (tvNoAlerts != null) tvNoAlerts.setVisibility(View.GONE);
                for (DashboardResponse.AlertHistoryItem item : data.recentAlerts) {
                    View itemView = getLayoutInflater().inflate(R.layout.item_alert_history, layoutAlertsList, false);
                    TextView tvType = itemView.findViewById(R.id.tvAlertItemType);
                    TextView tvStatus = itemView.findViewById(R.id.tvAlertItemStatus);
                    TextView tvTarget = itemView.findViewById(R.id.tvAlertItemTarget);
                    TextView tvTime = itemView.findViewById(R.id.tvAlertItemTime);
                    TextView tvNotes = itemView.findViewById(R.id.tvAlertItemNotes);

                    tvType.setText(item.alertTypeDisplay != null ? item.alertTypeDisplay : item.alertType);

                    String statusStr = item.statusDisplay != null ? item.statusDisplay : item.status;
                    tvStatus.setText(statusStr);
                    if ("RESOLVED".equalsIgnoreCase(item.status)) {
                        tvStatus.setTextColor(getResources().getColor(R.color.success));
                        tvStatus.setBackgroundColor(getResources().getColor(R.color.success_bg));
                    } else if ("ACKNOWLEDGED".equalsIgnoreCase(item.status)) {
                        tvStatus.setTextColor(getResources().getColor(R.color.text_primary));
                        tvStatus.setBackgroundColor(getResources().getColor(R.color.surface_variant));
                    } else {
                        tvStatus.setTextColor(getResources().getColor(R.color.danger));
                        tvStatus.setBackgroundColor(getResources().getColor(R.color.error_bg));
                    }

                    String targetStr = "";
                    if (item.studentName != null && !item.studentName.isEmpty()) {
                        targetStr += item.studentName;
                        if (item.rollNumber != null && !item.rollNumber.isEmpty()) {
                            targetStr += " (" + item.rollNumber + ")";
                        }
                    } else {
                        targetStr += "General Hall Incident";
                    }
                    if (item.seat != null && !"-".equals(item.seat) && !item.seat.isEmpty()) {
                        targetStr += " · " + item.seat;
                    }
                    tvTarget.setText(targetStr);

                    tvTime.setText(item.timestampDisplay != null ? item.timestampDisplay : "");

                    if (item.notes != null && !item.notes.trim().isEmpty()) {
                        tvNotes.setVisibility(View.VISIBLE);
                        tvNotes.setText("\"" + item.notes.trim() + "\"");
                    } else {
                        tvNotes.setVisibility(View.GONE);
                    }

                    layoutAlertsList.addView(itemView);
                }
            } else {
                if (tvNoAlerts != null) tvNoAlerts.setVisibility(View.VISIBLE);
            }
        }
    }

    private void handleUnauthorized() {
        ApiClient.clearToken(this);
        startActivity(new Intent(this, LoginActivity.class));
        finish();
    }

    private void showError(String msg) {
        Toast.makeText(this, msg, Toast.LENGTH_SHORT).show();
    }

    // ── Options menu (logout) ────────────────────────────────────────────────
    @Override
    public boolean onCreateOptionsMenu(Menu menu) {
        getMenuInflater().inflate(R.menu.dashboard_menu, menu);
        return true;
    }

    @Override
    public boolean onOptionsItemSelected(MenuItem item) {
        if (item.getItemId() == R.id.action_change_server) {
            showChangeServerDialog();
            return true;
        }
        if (item.getItemId() == R.id.action_logout) {
            performLogout();
            return true;
        }
        return super.onOptionsItemSelected(item);
    }

    private void showChangeServerDialog() {
        final EditText input = new EditText(this);
        input.setText(ApiClient.getServerUrl(this));
        input.setSelection(input.getText().length());
        input.setPadding(40, 30, 40, 30);

        new androidx.appcompat.app.AlertDialog.Builder(this)
                .setTitle("Server URL")
                .setMessage("Current server URL. Update if switching networks or server hosts:")
                .setView(input)
                .setPositiveButton("Save & Reload", (dialog, which) -> {
                    String newUrl = input.getText().toString().trim();
                    if (!newUrl.isEmpty()) {
                        if (!newUrl.startsWith("http://") && !newUrl.startsWith("https://")) {
                            newUrl = "http://" + newUrl;
                        }
                        ApiClient.setServerUrl(DashboardActivity.this, newUrl);
                        loadDashboard();
                        Toast.makeText(DashboardActivity.this, "Server URL updated!", Toast.LENGTH_SHORT).show();
                    }
                })
                .setNegativeButton("Cancel", null)
                .show();
    }

    private void performLogout() {
        ApiClient.getApi(this).logout().enqueue(new Callback<SimpleResponse>() {
            @Override public void onResponse(Call<SimpleResponse> call, Response<SimpleResponse> r) {}
            @Override public void onFailure(Call<SimpleResponse> call, Throwable t) {}
        });
        ApiClient.clearToken(this);
        startActivity(new Intent(this, LoginActivity.class));
        finish();
    }
}
