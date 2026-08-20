import { Component, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule } from '@angular/router';

import { MatCardModule } from '@angular/material/card';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';

import { ApiService } from '../../../core/services/api.service';
import { finalize } from 'rxjs/operators';

interface DashboardStats {
  totalEmails: number;
  pendingTasks: number;
  drafts: number;
  needsReview: number;
}

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [
    CommonModule,
    RouterModule,
    MatCardModule,
    MatProgressSpinnerModule,
    MatButtonModule,
    MatIconModule,
  ],
  templateUrl: './dashboard.html',
  styleUrl: './dashboard.css',
})
export class Dashboard implements OnInit {

  stats = signal<DashboardStats | null>(null);

  loading = signal(true);
  error = signal(false);

  constructor(private api: ApiService) {}

  ngOnInit(): void {
    this.loadStats();
  }

  loadStats(): void {
    this.loading.set(true);
    this.error.set(false);

    this.api
      .get<DashboardStats>('/api/dashboard/stats')
      .pipe(
        finalize(() => {
          this.loading.set(false);
        })
      )
      .subscribe({
        next: (data: DashboardStats) => {
          this.stats.set(data);
        },

        error: (err) => {
          console.error('Failed to load dashboard:', err);
          this.stats.set(null);
          this.error.set(true);
        },
      });
  }
}