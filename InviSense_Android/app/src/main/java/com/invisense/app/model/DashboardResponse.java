package com.invisense.app.model;

import com.google.gson.annotations.SerializedName;
import java.util.List;

public class DashboardResponse {
    @SerializedName("status")           public String  status;
    @SerializedName("has_active_exam")  public boolean hasActiveExam;
    @SerializedName("scan_open")        public boolean scanOpen;
    @SerializedName("message")          public String  message;
    @SerializedName("exam")             public ExamInfo exam;
    @SerializedName("invigilator")      public InvigilatorInfo invigilator;
    @SerializedName("upcoming_exams")   public List<UpcomingExamInfo> upcomingExams;
    @SerializedName("recent_alerts")    public List<AlertHistoryItem> recentAlerts;

    public static class InvigilatorInfo {
        @SerializedName("id")        public int id;
        @SerializedName("username")  public String username;
        @SerializedName("name")      public String name;
        @SerializedName("full_name") public String fullName;
    }

    public static class UpcomingExamInfo {
        @SerializedName("exam_session_id") public int    examSessionId;
        @SerializedName("exam_hall_id")    public int    examHallId;
        @SerializedName("subject")         public String subject;
        @SerializedName("exam_date")       public String examDate;
        @SerializedName("start_time")      public String startTime;
        @SerializedName("end_time")        public String endTime;
        @SerializedName("hall_name")       public String hallName;
        @SerializedName("total_students")  public int    totalStudents;
        @SerializedName("scan_opens_at")   public String scanOpensAt;
    }

    public static class ExamInfo {
        @SerializedName("subject")         public String subject;
        @SerializedName("exam_date")       public String examDate;
        @SerializedName("start_time")      public String startTime;
        @SerializedName("end_time")        public String endTime;
        @SerializedName("hall_name")       public String hallName;
        @SerializedName("scan_opens_at")   public String scanOpensAt;
        @SerializedName("present_count")   public int    presentCount;
        @SerializedName("total_assigned")  public int    totalAssigned;
        @SerializedName("is_ended")        public boolean isEnded;
        @SerializedName("is_scanning_open") public boolean isScanningOpen;
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
