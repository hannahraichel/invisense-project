package com.invisense.app.ui.dashboard;

import android.content.Intent;
import android.os.Bundle;
import android.view.MenuItem;
import android.view.View;
import android.widget.ProgressBar;
import android.widget.TextView;
import android.widget.Toast;

import androidx.appcompat.app.AppCompatActivity;
import androidx.appcompat.widget.Toolbar;
import androidx.recyclerview.widget.LinearLayoutManager;
import androidx.recyclerview.widget.RecyclerView;
import androidx.swiperefreshlayout.widget.SwipeRefreshLayout;

import com.invisense.app.R;
import com.invisense.app.api.ApiClient;
import com.invisense.app.model.RosterResponse;
import com.invisense.app.ui.login.LoginActivity;

import java.util.ArrayList;

import retrofit2.Call;
import retrofit2.Callback;
import retrofit2.Response;

public class RosterActivity extends AppCompatActivity {

    private RecyclerView     recyclerView;
    private ProgressBar      progressBar;
    private TextView         tvSummary, tvEmpty;
    private SwipeRefreshLayout swipeRefresh;
    private RosterAdapter    adapter;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_roster);

        Toolbar toolbar = findViewById(R.id.toolbar);
        setSupportActionBar(toolbar);
        if (getSupportActionBar() != null) getSupportActionBar().setDisplayHomeAsUpEnabled(true);

        recyclerView = findViewById(R.id.recyclerView);
        progressBar  = findViewById(R.id.progressBar);
        tvSummary    = findViewById(R.id.tvSummary);
        tvEmpty      = findViewById(R.id.tvEmpty);
        swipeRefresh = findViewById(R.id.swipeRefresh);

        adapter = new RosterAdapter(new ArrayList<>());
        recyclerView.setLayoutManager(new LinearLayoutManager(this));
        recyclerView.setAdapter(adapter);

        swipeRefresh.setOnRefreshListener(this::loadRoster);
        loadRoster();
    }

    private void loadRoster() {
        progressBar.setVisibility(View.VISIBLE);
        ApiClient.getApi(this).getRoster().enqueue(new Callback<RosterResponse>() {
            @Override
            public void onResponse(Call<RosterResponse> call, Response<RosterResponse> response) {
                progressBar.setVisibility(View.GONE);
                swipeRefresh.setRefreshing(false);
                if (!response.isSuccessful() || response.body() == null) {
                    if (response.code() == 401) { handleUnauth(); return; }
                    Toast.makeText(RosterActivity.this, "Could not load roster.", Toast.LENGTH_SHORT).show();
                    return;
                }
                RosterResponse body = response.body();
                tvSummary.setText(body.presentCount + " / " + body.totalCount + " checked in");
                adapter.update(body.students);
                tvEmpty.setVisibility(body.students.isEmpty() ? View.VISIBLE : View.GONE);
                recyclerView.setVisibility(body.students.isEmpty() ? View.GONE : View.VISIBLE);
            }
            @Override
            public void onFailure(Call<RosterResponse> call, Throwable t) {
                progressBar.setVisibility(View.GONE);
                swipeRefresh.setRefreshing(false);
                Toast.makeText(RosterActivity.this, "Network error.", Toast.LENGTH_SHORT).show();
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
