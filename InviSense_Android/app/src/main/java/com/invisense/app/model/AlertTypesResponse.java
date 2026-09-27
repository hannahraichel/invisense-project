package com.invisense.app.model;
import com.google.gson.annotations.SerializedName;
import java.util.List;

public class AlertTypesResponse {
    @SerializedName("alert_types") public List<AlertType> alertTypes;

    public static class AlertType {
        @SerializedName("code")  public String value;   // backend sends "code"
        @SerializedName("label") public String label;
    }
}
