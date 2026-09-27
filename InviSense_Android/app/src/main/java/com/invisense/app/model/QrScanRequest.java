package com.invisense.app.model;

import com.google.gson.annotations.SerializedName;

public class QrScanRequest {
    @SerializedName("qr_data") public String qrData;
    public QrScanRequest(String qrData) { this.qrData = qrData; }
}
