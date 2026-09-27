package com.invisense.app.ui.dashboard;

import android.content.Intent;
import android.os.Bundle;
import android.os.Handler;
import android.view.Menu;
import android.view.MenuItem;
import android.view.View;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.TextView;
import android.widget.Toast;

import androidx.appcompat.app.AppCompatActivity;
import androidx.appcompat.widget.Toolbar;
import androidx.cardview.widget.CardView;
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

    private TextView tvAvatarBadge, tvTeacherName, tvTeacherRole;
    private TextView tvSubject, tvHall, tvTime, tvStatus, tvPresent, tvScanWindow;
    private Button   btnScan, btnAlert, btnRoster;
    private LinearLayout layoutExam, layoutNoExam, layoutAlertsList, layoutUpcomingList;
    private CardView cardUpcomingExams, cardAlertHistory;
    private TextView tvNoAlerts;
    private ProgressBar  progressBar;
    private SwipeRefreshLayout swipeRefresh;

    private boolean isExamEnded = false;
    private boolean isScanningOpen = false;

    private Handler  autoRefreshHandler = new Handler();
    private Runnable autoRefreshRunnable;
    private static final int REFRESH_INTERVAL_MS = 30_000; // 30 seconds

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_dashboard);

        Toolbar toolbar = findViewById(R.id.toolbar);
        setSupportActionBar(toolbar);

        tvAvatarBadge    = findViewById(R.id.tvAvatarBadge);
        tvTeacherName    = findViewById(R.id.tvTeacherName);
        tvTeacherRole    = findViewById(R.id.tvTeacherRole);

        tvSubject        = findViewById(R.id.tvSubject);
        tvHall           = findViewById(R.id.tvHall);
        tvTime           = findViewById(R.id.tvTime);
        tvStatus         = findViewById(R.id.tvStatus);
        tvPresent        = findViewById(R.id.tvPresent);
        tvScanWindow     = findViewById(R.id.tvScanWindow);
        btnScan          = findViewById(R.id.btnScan);
        btnAlert         = findViewById(R.id.btnAlert);
        btnRoster        = findViewById(R.id.btnRoster);
        layoutExam       = findViewById(R.id.layoutExam);
        layoutNoExam     = findViewById(R.id.layoutNoExam);
        layoutAlertsList = findViewById(R.id.layoutAlertsList);
        layoutUpcomingList = findViewById(R.id.layoutUpcomingList);
        cardUpcomingExams = findViewById(R.id.cardUpcomingExams);
        cardAlertHistory = findViewById(R.id.cardAlertHistory);
        tvNoAlerts       = findViewById(R.id.tvNoAlerts);
        progressBar      = findViewById(R.id.progressBar);
        swipeRefresh     = findViewById(R.id.swipeRefresh);

        btnScan.setOnClickListener(v -> {
            if (isExamEnded) {
                Toast.makeText(this, "Scanning is closed because the exam has ended.", Toast.LENGTH_SHORT).show();
                return;
            }
            if (!isScanningOpen) {
                Toast.makeText(this, "Scanning is not open yet.", Toast.LENGTH_SHORT).show();
                return;
            }
            startActivity(new Intent(this, ScanActivity.class));
        });

        btnAlert.setOnClickListener(v -> {
            if (isExamEnded) {
                Toast.makeText(this, "You cannot raise an alert after the exam has ended.", Toast.LENGTH_LONG).show();
                return;
            }
            startActivity(new Intent(this, AlertActivity.class));
        });

        // Student Roster is ALWAYS accessible
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
        // Teacher name & avatar in top profile card
        if (data.invigilator != null) {
            String fullName = data.invigilator.fullName != null && !data.invigilator.fullName.isEmpty()
                    ? data.invigilator.fullName
                    : (data.invigilator.name != null && !data.invigilator.name.isEmpty() ? data.invigilator.name : data.invigilator.username);
            tvTeacherName.setText(fullName != null ? fullName : "Invigilator");

            if (fullName != null && !fullName.trim().isEmpty()) {
                String[] parts = fullName.trim().split("\\s+");
                String initials = "";
                if (parts.length >= 2) {
                    initials = ("" + parts[0].charAt(0) + parts[1].charAt(0)).toUpperCase();
                } else if (parts[0].length() >= 2) {
                    initials = parts[0].substring(0, 2).toUpperCase();
                } else {
                    initials = parts[0].toUpperCase();
                }
                tvAvatarBadge.setText(initials);
            }
        }

        // Active / Ended / Today's Exam Card
        if (data.exam != null) {
            layoutExam.setVisibility(View.VISIBLE);
            layoutNoExam.setVisibility(View.GONE);

            tvSubject.setText(data.exam.subject);
            tvHall.setText("Assigned Hall: " + data.exam.hallName);
            tvTime.setText(data.exam.startTime + " – " + data.exam.endTime + " (" + data.exam.examDate + ")");
            tvPresent.setText(data.exam.presentCount + " / " + data.exam.totalAssigned + " students checked in");

            isExamEnded = data.exam.isEnded;
            isScanningOpen = data.scanOpen;

            if (isExamEnded) {
                tvStatus.setText("⚫  EXAM ENDED");
                tvStatus.setTextColor(getResources().getColor(R.color.secondary));
                tvStatus.setBackgroundColor(getResources().getColor(R.color.surface_variant));

                tvScanWindow.setText("This examination session has concluded.\nAttendance roster is available for review.");
                tvScanWindow.setVisibility(View.VISIBLE);

                btnScan.setEnabled(false);
                btnScan.setText("Exam Concluded (Scan Closed)");

                // Alert button indicates closed
                btnAlert.setText("Incident Alerts Closed (Exam Ended)");
                btnAlert.setAlpha(0.6f);
            } else if (isScanningOpen) {
                tvStatus.setText("🟢  Scanning OPEN");
                tvStatus.setTextColor(getResources().getColor(R.color.success));
                tvStatus.setBackgroundColor(getResources().getColor(R.color.success_bg));

                tvScanWindow.setVisibility(View.GONE);

                btnScan.setEnabled(true);
                btnScan.setText("Scan Student QR Code");

                btnAlert.setText("Raise Incident Alert");
                btnAlert.setAlpha(1.0f);
            } else {
                tvStatus.setText("🔴  Scanning LOCKED");
                tvStatus.setTextColor(getResources().getColor(R.color.warning));
                tvStatus.setBackgroundColor(getResources().getColor(R.color.warning_bg));

                tvScanWindow.setText("Scanning opens 3 hours before start time\n(at " + data.exam.scanOpensAt + ")");
                tvScanWindow.setVisibility(View.VISIBLE);

                btnScan.setEnabled(false);
                btnScan.setText("Scanning Not Yet Open");

                btnAlert.setText("Raise Incident Alert");
                btnAlert.setAlpha(1.0f);
            }

            // Student Roster button is ALWAYS enabled!
            btnRoster.setEnabled(true);
            btnRoster.setText("View Student Roster (" + data.exam.totalAssigned + ")");
        } else {
            layoutExam.setVisibility(View.GONE);
            layoutNoExam.setVisibility(View.VISIBLE);
            String msg = data.message != null ? data.message : "No exam assigned right now.";
            ((TextView) layoutNoExam.findViewById(R.id.tvNoExamMsg)).setText(msg);
        }

        // Render Upcoming Exams (Tomorrow / Day After / Later)
        if (data.upcomingExams != null && !data.upcomingExams.isEmpty()) {
            cardUpcomingExams.setVisibility(View.VISIBLE);
            layoutUpcomingList.removeAllViews();
            for (DashboardResponse.UpcomingExamInfo item : data.upcomingExams) {
                View itemView = getLayoutInflater().inflate(R.layout.item_upcoming_exam, layoutUpcomingList, false);
                TextView tvSub = itemView.findViewById(R.id.tvUpcomingSubject);
                TextView tvDate = itemView.findViewById(R.id.tvUpcomingDate);
                TextView tvHallTime = itemView.findViewById(R.id.tvUpcomingHallTime);
                TextView tvScanOpens = itemView.findViewById(R.id.tvUpcomingScanOpens);

                tvSub.setText(item.subject);
                tvDate.setText(item.examDate);
                tvHallTime.setText(item.hallName + " · " + item.startTime + " – " + item.endTime + " (" + item.totalStudents + " students)");
                tvScanOpens.setText("Scanning opens: " + item.scanOpensAt);

                layoutUpcomingList.addView(itemView);
            }
        } else {
            cardUpcomingExams.setVisibility(View.GONE);
        }

        // Render Flagged Incidents History
        if (layoutAlertsList != null) {
            layoutAlertsList.removeAllViews();
            if (data.recentAlerts != null && !data.recentAlerts.isEmpty()) {
                if (tvNoAlerts != null) tvNoAlerts.setVisibility(View.GONE);
                for (DashboardResponse.AlertHistoryItem item : data.recentAlerts) {
                    View itemView = getLayoutInflater().inflate(R.layout.item_alert_history, layoutAlertsList, false);
                    TextView tvType = itemView.findViewById(R.id.tvAlertItemType);
                    TextView tvItemStatus = itemView.findViewById(R.id.tvAlertItemStatus);
                    TextView tvTarget = itemView.findViewById(R.id.tvAlertItemTarget);
                    TextView tvItemTime = itemView.findViewById(R.id.tvAlertItemTime);
                    TextView tvNotes = itemView.findViewById(R.id.tvAlertItemNotes);

                    tvType.setText(item.alertTypeDisplay != null ? item.alertTypeDisplay : item.alertType);

                    String statusStr = item.statusDisplay != null ? item.statusDisplay : item.status;
                    tvItemStatus.setText(statusStr);
                    if ("RESOLVED".equalsIgnoreCase(item.status)) {
                        tvItemStatus.setTextColor(getResources().getColor(R.color.success));
                        tvItemStatus.setBackgroundColor(getResources().getColor(R.color.success_bg));
                    } else if ("ACKNOWLEDGED".equalsIgnoreCase(item.status)) {
                        tvItemStatus.setTextColor(getResources().getColor(R.color.text_primary));
                        tvItemStatus.setBackgroundColor(getResources().getColor(R.color.surface_variant));
                    } else {
                        tvItemStatus.setTextColor(getResources().getColor(R.color.danger));
                        tvItemStatus.setBackgroundColor(getResources().getColor(R.color.error_bg));
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

                    tvItemTime.setText(item.timestampDisplay != null ? item.timestampDisplay : "");

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

    // ── Options menu ──────────────────────────────────────────────────────────
    @Override
    public boolean onCreateOptionsMenu(Menu menu) {
        getMenuInflater().inflate(R.menu.dashboard_menu, menu);
        return true;
    }

    @Override
    public boolean onOptionsItemSelected(MenuItem item) {
        if (item.getItemId() == R.id.action_refresh) {
            loadDashboard();
            return true;
        }
        if (item.getItemId() == R.id.action_logout) {
            performLogout();
            return true;
        }
        return super.onOptionsItemSelected(item);
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
