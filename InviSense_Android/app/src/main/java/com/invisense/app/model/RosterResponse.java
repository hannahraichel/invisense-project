package com.invisense.app.model;

import com.google.gson.annotations.SerializedName;
import java.util.List;

public class RosterResponse {
    @SerializedName("students")      public List<Student> students;
    @SerializedName("present_count") public int presentCount;
    @SerializedName("total_count")   public int totalCount;

    public static class Student {
        @SerializedName("id")          public int     id;
        @SerializedName("roll_number") public String  rollNumber;
        @SerializedName("name")        public String  name;
        @SerializedName("row")         public String  row;
        @SerializedName("seat")        public String  seat;
        @SerializedName("is_present")  public boolean isPresent;
    }
}
