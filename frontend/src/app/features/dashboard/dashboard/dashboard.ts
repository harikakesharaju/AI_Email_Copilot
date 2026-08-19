import { Component, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule } from '@angular/router';
import { MatCardModule } from '@angular/material/card';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';

import { ApiService } from '../../../core/services/api.service';

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
    CommonModule, RouterModule,
    MatCardModule, MatProgressSpinnerModule, MatButtonModule, MatIconModule,
  ],
  templateUrl: './dashboard.html',
  styleUrl: './dashboard.css',
})
export class Dashboard implements OnInit {
  stats = signal<DashboardStats | null>(null);
  loading = true;
  error = false;

  constructor(private api: ApiService) {}

  ngOnInit(): void {
    this.loadStats();
  }

  loadStats(): void {
    this.loading = true;
    this.error = false;
    this.api.get<DashboardStats>('/api/dashboard/stats').subscribe({
      next: (data) => { this.stats.set(data); this.loading = false; },
      error: () => { this.loading = false; this.error = true; },
    });
  }
}
