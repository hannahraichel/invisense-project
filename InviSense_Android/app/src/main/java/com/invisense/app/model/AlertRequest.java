package com.invisense.app.model;

import com.google.gson.annotations.SerializedName;

public class AlertRequest {
    @SerializedName("alert_type") public String alertType;
    @SerializedName("student_id") public Integer studentId;
    @SerializedName("row")        public String row;
    @SerializedName("seat")       public String seat;
    @SerializedName("notes")      public String notes;
}
