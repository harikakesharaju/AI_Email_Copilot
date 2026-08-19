import { Component, OnInit, signal, computed } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';

import { MatTableModule } from '@angular/material/table';
import { MatCardModule } from '@angular/material/card';
import { MatChipsModule } from '@angular/material/chips';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatIconModule } from '@angular/material/icon';

import { Email } from '../../../core/models/email.model';
import { EmailService } from '../../../core/services/email.service';
import { finalize } from 'rxjs/operators';

@Component({
  selector: 'app-emails',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    MatTableModule,
    MatCardModule,
    MatChipsModule,
    MatFormFieldModule,
    MatInputModule,
    MatProgressSpinnerModule,
    MatIconModule
  ],
  templateUrl: './emails.html',
  styleUrl: './emails.css'
})
export class Emails implements OnInit {

  emails = signal<Email[]>([]);

  loading = true;

  searchText = '';

  displayedColumns = [
    'sender',
    'summary',
    'category',
    'priority',
    'confidence',
    'needs_manual_review',
    'received_at'
  ];

  constructor(
    private emailService: EmailService
  ) {}

  ngOnInit(): void {

    this.loadEmails();

  }

  loadEmails() {

    this.loading = true;

    this.emailService.getEmails().pipe(
      finalize(() => { this.loading = false; })
    ).subscribe({
      next: (data: Email[]) => {
        this.emails.set(data);
      },
      error: (err) => {
        console.error(err);
      }
    });

  }

  filteredEmails = computed(() => {

    const search = this.searchText.toLowerCase();

    if (!search) {
      return this.emails();
    }

    return this.emails().filter(email =>
      (email.sender ?? '').toLowerCase().includes(search) ||
      (email.summary ?? '').toLowerCase().includes(search)
    );

  });

  getSenderName(email: string): string {
    return (email ?? '').split('@')[0];
  }

}