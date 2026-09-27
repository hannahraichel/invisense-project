package com.invisense.app.model;

import com.google.gson.annotations.SerializedName;

public class LoginResponse {
    @SerializedName("status")  public String status;
    @SerializedName("token")   public String token;
    @SerializedName("message") public String message;
    @SerializedName("user")    public UserInfo user;

    public static class UserInfo {
        @SerializedName("username")   public String username;
        @SerializedName("full_name")  public String fullName;
        @SerializedName("role")       public String role;
    }
}
