package com.invisense.app.ui.alert;

import android.content.Intent;
import android.os.Bundle;
import android.view.MenuItem;
import android.view.View;
import android.widget.ArrayAdapter;
import android.widget.EditText;
import android.widget.ProgressBar;
import android.widget.Spinner;
import android.widget.Toast;

import androidx.appcompat.app.AppCompatActivity;
import androidx.appcompat.widget.Toolbar;

import com.invisense.app.R;
import com.invisense.app.api.ApiClient;
import com.invisense.app.model.AlertRequest;
import com.invisense.app.model.AlertTypesResponse;
import com.invisense.app.model.RosterResponse;
import com.invisense.app.model.SimpleResponse;
import com.invisense.app.ui.login.LoginActivity;

import java.util.ArrayList;
import java.util.List;

import retrofit2.Call;
import retrofit2.Callback;
import retrofit2.Response;

public class AlertActivity extends AppCompatActivity {

    private Spinner     spinnerAlertType;
    private Spinner     spinnerStudent;
    private EditText    etNotes;
    private View        btnSubmit, btnCancel;
    private ProgressBar progressBar;

    private List<AlertTypesResponse.AlertType> alertTypeList = new ArrayList<>();
    // Only scanned (present) students
    private List<RosterResponse.Student>       scannedStudents = new ArrayList<>();

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_alert);

        Toolbar toolbar = findViewById(R.id.toolbar);
        setSupportActionBar(toolbar);
        if (getSupportActionBar() != null) {
            getSupportActionBar().setDisplayHomeAsUpEnabled(true);
            getSupportActionBar().setDisplayShowHomeEnabled(true);
        }
        toolbar.setNavigationOnClickListener(v -> finish());

        spinnerAlertType = findViewById(R.id.spinnerAlertType);
        spinnerStudent   = findViewById(R.id.spinnerStudent);
        etNotes          = findViewById(R.id.etNotes);
        btnSubmit        = findViewById(R.id.btnSubmit);
        btnCancel        = findViewById(R.id.btnCancel);
        progressBar      = findViewById(R.id.progressBar);

        loadAlertTypes();
        loadScannedStudents();

        btnSubmit.setOnClickListener(v -> submitAlert());
        btnCancel.setOnClickListener(v -> finish());
    }

    // ─── Load alert type options from server ───────────────────────────────────
    private void loadAlertTypes() {
        ApiClient.getApi(this).getAlertTypes().enqueue(new Callback<AlertTypesResponse>() {
            @Override
            public void onResponse(Call<AlertTypesResponse> call, Response<AlertTypesResponse> response) {
                if (response.isSuccessful() && response.body() != null
                        && response.body().alertTypes != null) {
                    alertTypeList = response.body().alertTypes;
                    populateAlertTypeSpinner();
                } else {
                    useDefaultAlertTypes();
                }
            }
            @Override public void onFailure(Call<AlertTypesResponse> call, Throwable t) {
                useDefaultAlertTypes();
            }
        });
    }

    private void populateAlertTypeSpinner() {
        List<String> labels = new ArrayList<>();
        for (AlertTypesResponse.AlertType t : alertTypeList) labels.add(t.label);
        ArrayAdapter<String> adapter = new ArrayAdapter<>(this,
                android.R.layout.simple_spinner_item, labels);
        adapter.setDropDownViewResource(android.R.layout.simple_spinner_dropdown_item);
        spinnerAlertType.setAdapter(adapter);
    }

    private void useDefaultAlertTypes() {
        // Fallback choices
        String[][] defaults = {
            {"NEED_SUPERVISOR",      "Need Supervisor"},
            {"SUSPICIOUS_ACTIVITY",  "Suspicious Activity"},
            {"MEDICAL_EMERGENCY",    "Medical Emergency"},
            {"OTHER",                "Other"}
        };
        alertTypeList = new ArrayList<>();
        List<String> labels = new ArrayList<>();
        for (String[] d : defaults) {
            AlertTypesResponse.AlertType t = new AlertTypesResponse.AlertType();
            t.value = d[0]; t.label = d[1];
            alertTypeList.add(t);
            labels.add(d[1]);
        }
        ArrayAdapter<String> adapter = new ArrayAdapter<>(this,
                android.R.layout.simple_spinner_item, labels);
        adapter.setDropDownViewResource(android.R.layout.simple_spinner_dropdown_item);
        spinnerAlertType.setAdapter(adapter);
    }

    // ─── Load roster, keep only scanned (present) students ───────────────────
    private void loadScannedStudents() {
        ApiClient.getApi(this).getRoster().enqueue(new Callback<RosterResponse>() {
            @Override
            public void onResponse(Call<RosterResponse> call, Response<RosterResponse> response) {
                if (response.isSuccessful() && response.body() != null) {
                    scannedStudents = new ArrayList<>();
                    if (response.body().students != null) {
                        for (RosterResponse.Student s : response.body().students) {
                            if (s.isPresent) scannedStudents.add(s);
                        }
                    }
                }
                populateStudentSpinner();
            }
            @Override public void onFailure(Call<RosterResponse> call, Throwable t) {
                populateStudentSpinner();
            }
        });
    }

    private void populateStudentSpinner() {
        List<String> items = new ArrayList<>();
        items.add("-- No specific student (General Hall Issue) --");
        for (RosterResponse.Student s : scannedStudents) {
            String seatInfo = "";
            if (s.row != null && !s.row.isEmpty()) seatInfo += "Row " + s.row;
            if (s.seat != null && !s.seat.isEmpty()) {
                if (!seatInfo.isEmpty()) seatInfo += ", ";
                seatInfo += "Seat " + s.seat;
            }
            if (!seatInfo.isEmpty()) seatInfo = "  [" + seatInfo + "]";

            String nameStr = (s.name != null && !s.name.isEmpty()) ? s.name : s.rollNumber;
            items.add(nameStr + " (" + s.rollNumber + ")" + seatInfo);
        }
        ArrayAdapter<String> adapter = new ArrayAdapter<>(this,
                android.R.layout.simple_spinner_item, items);
        adapter.setDropDownViewResource(android.R.layout.simple_spinner_dropdown_item);
        spinnerStudent.setAdapter(adapter);
    }

    // ─── Submit ───────────────────────────────────────────────────────────────
    private void submitAlert() {
        if (alertTypeList.isEmpty()) {
            Toast.makeText(this, "Alert types not loaded yet. Please wait.", Toast.LENGTH_SHORT).show();
            return;
        }

        int typeIdx = spinnerAlertType.getSelectedItemPosition();
        if (typeIdx < 0 || typeIdx >= alertTypeList.size()) {
            Toast.makeText(this, "Please select an alert type.", Toast.LENGTH_SHORT).show();
            return;
        }

        String notes = etNotes.getText().toString().trim();
        AlertRequest req = new AlertRequest();
        req.alertType = alertTypeList.get(typeIdx).value;
        req.notes = notes.isEmpty() ? null : notes;

        // Auto-populate row & seat directly from the chosen student
        int studentIdx = spinnerStudent.getSelectedItemPosition();
        if (studentIdx > 0 && studentIdx <= scannedStudents.size()) {
            RosterResponse.Student s = scannedStudents.get(studentIdx - 1);
            req.studentId = s.id;
            req.row = s.row;
            req.seat = s.seat;
        } else {
            req.studentId = null;
            req.row = null;
            req.seat = null;
        }

        progressBar.setVisibility(View.VISIBLE);
        btnSubmit.setEnabled(false);

        ApiClient.getApi(this).raiseAlert(req).enqueue(new Callback<SimpleResponse>() {
            @Override
            public void onResponse(Call<SimpleResponse> call, Response<SimpleResponse> response) {
                progressBar.setVisibility(View.GONE);
                btnSubmit.setEnabled(true);

                if (response.isSuccessful() && response.body() != null
                        && "success".equals(response.body().status)) {
                    Toast.makeText(AlertActivity.this,
                            "✅ Alert raised. Control room notified.", Toast.LENGTH_LONG).show();
                    finish();
                } else if (response.code() == 401) {
                    handleUnauth();
                } else {
                    String msg = (response.body() != null && response.body().message != null)
                            ? response.body().message : "Failed to raise alert.";
                    Toast.makeText(AlertActivity.this, msg, Toast.LENGTH_SHORT).show();
                }
            }
            @Override
            public void onFailure(Call<SimpleResponse> call, Throwable t) {
                progressBar.setVisibility(View.GONE);
                btnSubmit.setEnabled(true);
                Toast.makeText(AlertActivity.this, "Network error. Check connection.", Toast.LENGTH_SHORT).show();
            }
        });
    }

    private void handleUnauth() {
        ApiClient.clearToken(this);
        startActivity(new Intent(this, LoginActivity.class));
        finish();
    }

    @Override
    public boolean onOptionsItemSelected(MenuItem item) {
        if (item.getItemId() == android.R.id.home) { finish(); return true; }
        return super.onOptionsItemSelected(item);
    }
}
