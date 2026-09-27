package com.invisense.app.model;
import com.google.gson.annotations.SerializedName;
public class SimpleResponse {
    @SerializedName("status")  public String status;
    @SerializedName("message") public String message;
}
