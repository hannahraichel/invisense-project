package com.invisense.app.model;

import com.google.gson.annotations.SerializedName;

public class QrScanResponse {
    @SerializedName("status")     public String status;   // "success", "warning", "error"
    @SerializedName("message")    public String message;
    @SerializedName("student_id") public Integer studentId;
}
