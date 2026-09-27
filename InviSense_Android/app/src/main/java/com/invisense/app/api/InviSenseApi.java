package com.invisense.app.api;

import com.invisense.app.model.AlertRequest;
import com.invisense.app.model.AlertTypesResponse;
import com.invisense.app.model.DashboardResponse;
import com.invisense.app.model.LoginRequest;
import com.invisense.app.model.LoginResponse;
import com.invisense.app.model.QrScanRequest;
import com.invisense.app.model.QrScanResponse;
import com.invisense.app.model.RosterResponse;
import com.invisense.app.model.SimpleResponse;

import retrofit2.Call;
import retrofit2.http.Body;
import retrofit2.http.GET;
import retrofit2.http.POST;

/**
 * Maps to the InviSense invigilator REST API endpoints.
 */
public interface InviSenseApi {

    /** POST /api/invigilator/login/ */
    @POST("api/invigilator/login/")
    Call<LoginResponse> login(@Body LoginRequest body);

    /** POST /api/invigilator/logout/ */
    @POST("api/invigilator/logout/")
    Call<SimpleResponse> logout();

    /** GET /api/invigilator/dashboard/ — exam context + scan window status */
    @GET("api/invigilator/dashboard/")
    Call<DashboardResponse> getDashboard();

    /** GET /api/invigilator/roster/ — student list for current hall */
    @GET("api/invigilator/roster/")
    Call<RosterResponse> getRoster();

    /** POST /api/invigilator/verify-qr/ — scan a QR code */
    @POST("api/invigilator/verify-qr/")
    Call<QrScanResponse> verifyQr(@Body QrScanRequest body);

    /** POST /api/invigilator/raise-alert/ — raise an incident */
    @POST("api/invigilator/raise-alert/")
    Call<SimpleResponse> raiseAlert(@Body AlertRequest body);

    /** GET /api/invigilator/alert-types/ — list of alert type options */
    @GET("api/invigilator/alert-types/")
    Call<AlertTypesResponse> getAlertTypes();
}
