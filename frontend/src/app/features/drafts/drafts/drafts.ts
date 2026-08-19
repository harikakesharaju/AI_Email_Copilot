import { Component, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';

import { MatCardModule } from '@angular/material/card';
import { MatButtonModule } from '@angular/material/button';
import { MatChipsModule } from '@angular/material/chips';
import { MatSnackBar, MatSnackBarModule } from '@angular/material/snack-bar';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { FormsModule } from '@angular/forms';

import { MatIconModule } from '@angular/material/icon';
import { Draft } from '../../../core/models/draft.model';
import { DraftService } from '../../../core/services/draft.service';
import { finalize } from 'rxjs/operators';

@Component({
  selector: 'app-drafts',
  standalone: true,
  imports: [CommonModule, FormsModule, MatCardModule, MatButtonModule, MatChipsModule, MatSnackBarModule, MatProgressSpinnerModule, MatIconModule],
  templateUrl: './drafts.html',
  styleUrl: './drafts.css',
})
export class Drafts implements OnInit {
  drafts = signal<Draft[]>([]);
  loading = true;

  constructor(private draftService: DraftService, private snackBar: MatSnackBar) {}

  ngOnInit(): void {
    this.loadDrafts();
  }

  loadDrafts(): void {
    this.loading = true;
    this.draftService.getDrafts().pipe(
      finalize(() => { this.loading = false; })
    ).subscribe({
      next: (data: Draft[]) => {
        this.drafts.set(data);
      },
      error: (err: any) => {
        console.error(err);
      },
    });
  }

  copy(text: string): void {
    navigator.clipboard.writeText(text);
    this.snackBar.open('Draft copied', 'Close', { duration: 2500 });
  }

  approveDraft(id: string): void {
    this.draftService.approveDraft(id).subscribe({
      next: () => {
        this.snackBar.open('Draft approved', 'Close', { duration: 2500 });
        this.loadDrafts();
      },
      error: (err: any) => {
        console.error(err);
        this.snackBar.open('Unable to approve draft', 'Close', { duration: 3000 });
      },
    });
  }

  sendDraft(id: string): void {
    this.draftService.sendDraft(id).subscribe({
      next: () => {
        this.snackBar.open('Email sent successfully', 'Close', { duration: 3000 });
        this.loadDrafts();
      },
      error: (err: any) => {
        console.error(err);
        this.snackBar.open(err?.error?.detail || 'Failed to send email.', 'Close', { duration: 4000 });
      },
    });
  }

  editDraft(draft: Draft): void {
    const updated = prompt('Edit Draft', draft.content);

    if (!updated || updated.trim() === '') {
      return;
    }

    this.draftService.editDraft(draft.id, updated).subscribe({
      next: () => {
        this.snackBar.open('Draft updated', 'Close', { duration: 2500 });
        this.loadDrafts();
      },
      error: (err: any) => {
        console.error(err);
        this.snackBar.open('Unable to update draft.', 'Close', { duration: 3000 });
      },
    });
  }
}
