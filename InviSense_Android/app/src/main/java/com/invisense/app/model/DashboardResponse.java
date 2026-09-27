package com.invisense.app.model;

import com.google.gson.annotations.SerializedName;
import java.util.List;

public class DashboardResponse {
    @SerializedName("status")           public String  status;
    @SerializedName("has_active_exam")  public boolean hasActiveExam;
    @SerializedName("scan_open")        public boolean scanOpen;
    @SerializedName("message")          public String  message;
    @SerializedName("exam")             public ExamInfo exam;
    @SerializedName("recent_alerts")    public List<AlertHistoryItem> recentAlerts;

    public static class ExamInfo {
        @SerializedName("subject")         public String subject;
        @SerializedName("exam_date")       public String examDate;
        @SerializedName("start_time")      public String startTime;
        @SerializedName("end_time")        public String endTime;
        @SerializedName("hall_name")       public String hallName;
        @SerializedName("scan_opens_at")   public String scanOpensAt;
        @SerializedName("present_count")   public int    presentCount;
        @SerializedName("total_assigned")  public int    totalAssigned;
    }

    public static class AlertHistoryItem {
        @SerializedName("id")                 public int    id;
        @SerializedName("alert_type")         public String alertType;
        @SerializedName("alert_type_display") public String alertTypeDisplay;
        @SerializedName("student_name")       public String studentName;
        @SerializedName("roll_number")        public String rollNumber;
        @SerializedName("seat")               public String seat;
        @SerializedName("hall_name")          public String hallName;
        @SerializedName("status")             public String status;
        @SerializedName("status_display")     public String statusDisplay;
        @SerializedName("timestamp_display")  public String timestampDisplay;
        @SerializedName("notes")              public String notes;
    }
}
