import { Component, OnInit, HostListener } from '@angular/core';
import { RouterLink, RouterLinkActive, Router } from '@angular/router';
import { NgIf } from '@angular/common';
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
    RouterLink,
    RouterLinkActive,
    NgIf,
    MatToolbarModule,
    MatButtonModule,
    MatIconModule,
  ],
  templateUrl: './navbar.html',
  styleUrl: './navbar.css'
})
export class Navbar implements OnInit {
  user: any = null;
  menuOpen = false;

  constructor(private api: ApiService, private router: Router) {}

  ngOnInit(): void {
    this.api.get<any>('/api/me').subscribe({
      next: (u) => (this.user = u),
      error: () => (this.user = null),
    });
  }

  logout(): void {
    this.api.post('/api/logout', {}).subscribe({
      next: () => {
        this.user = null;
        // Navigate to login after logout
        this.router.navigate(['/login']);
      },
      error: () => {
        this.user = null;
        this.router.navigate(['/login']);
      },
    });
  }

  toggleMenu(event: Event): void {
    event.stopPropagation();
    this.menuOpen = !this.menuOpen;
  }

  @HostListener('document:click', ['$event'])
  handleDocumentClick(_: Event) {
    this.menuOpen = false;
  }
}