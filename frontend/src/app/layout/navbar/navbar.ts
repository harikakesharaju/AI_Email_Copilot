import { Component, OnInit } from '@angular/core';
import { RouterLink, RouterLinkActive, Router } from '@angular/router';
import { CommonModule } from '@angular/common';
import { ApiService } from '../../core/services/api.service';

import { MatToolbarModule } from '@angular/material/toolbar';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatMenuModule } from '@angular/material/menu';
import { MatDividerModule } from '@angular/material/divider';

@Component({
  selector: 'app-navbar',
  standalone: true,
  imports: [
    RouterLink, RouterLinkActive, CommonModule,
    MatToolbarModule, MatButtonModule, MatIconModule, MatMenuModule, MatDividerModule,
  ],
  templateUrl: './navbar.html',
  styleUrl: './navbar.css',
})
export class Navbar implements OnInit {
  user: { id: string; email: string } | null = null;

  constructor(private api: ApiService, private router: Router) {}

  ngOnInit(): void {
    this.api.get<{ id: string; email: string }>('/api/me').subscribe({
      next: (u) => (this.user = u),
      error: () => (this.user = null),
    });
  }

  logout(): void {
    this.api.post('/api/logout', {}).subscribe({
      next: () => { this.user = null; this.router.navigate(['/login']); },
      error: () => { this.user = null; this.router.navigate(['/login']); },
    });
  }
}