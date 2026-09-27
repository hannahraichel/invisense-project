package com.invisense.app.ui.dashboard;

import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;
import android.widget.TextView;

import androidx.annotation.NonNull;
import androidx.core.content.ContextCompat;
import androidx.recyclerview.widget.RecyclerView;

import com.invisense.app.R;
import com.invisense.app.model.RosterResponse;

import java.util.List;

public class RosterAdapter extends RecyclerView.Adapter<RosterAdapter.ViewHolder> {

    private List<RosterResponse.Student> students;

    public RosterAdapter(List<RosterResponse.Student> students) {
        this.students = students;
    }

    public void update(List<RosterResponse.Student> newList) {
        this.students = newList;
        notifyDataSetChanged();
    }

    @NonNull
    @Override
    public ViewHolder onCreateViewHolder(@NonNull ViewGroup parent, int viewType) {
        View v = LayoutInflater.from(parent.getContext())
                .inflate(R.layout.item_student, parent, false);
        return new ViewHolder(v);
    }

    @Override
    public void onBindViewHolder(@NonNull ViewHolder holder, int position) {
        RosterResponse.Student s = students.get(position);
        holder.tvRoll.setText(s.rollNumber);
        holder.tvName.setText(s.name != null ? s.name : "");
        holder.tvSeat.setText("Row " + s.row + ", Seat " + s.seat);

        if (s.isPresent) {
            holder.tvStatus.setText("✓ Present");
            holder.tvStatus.setTextColor(
                    ContextCompat.getColor(holder.itemView.getContext(), R.color.success));
        } else {
            holder.tvStatus.setText("Absent");
            holder.tvStatus.setTextColor(
                    ContextCompat.getColor(holder.itemView.getContext(), R.color.muted));
        }
    }

    @Override public int getItemCount() { return students.size(); }

    static class ViewHolder extends RecyclerView.ViewHolder {
        TextView tvRoll, tvName, tvSeat, tvStatus;
        ViewHolder(View v) {
            super(v);
            tvRoll   = v.findViewById(R.id.tvRoll);
            tvName   = v.findViewById(R.id.tvName);
            tvSeat   = v.findViewById(R.id.tvSeat);
            tvStatus = v.findViewById(R.id.tvStatus);
        }
    }
}
