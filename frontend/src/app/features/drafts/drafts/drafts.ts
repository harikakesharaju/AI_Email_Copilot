import { Component, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';

import { MatCardModule } from '@angular/material/card';
import { MatButtonModule } from '@angular/material/button';
import { MatChipsModule } from '@angular/material/chips';
import { FormsModule } from '@angular/forms';

import { Draft } from '../../../core/models/draft.model';
import { DraftService } from '../../../core/services/draft.service';

@Component({
  selector: 'app-drafts',
  standalone: true,
  imports: [CommonModule, FormsModule, MatCardModule, MatButtonModule, MatChipsModule],
  templateUrl: './drafts.html',
  styleUrl: './drafts.css',
})
export class Drafts implements OnInit {
  drafts = signal<Draft[]>([]);
  snackBar: any;

  constructor(private draftService: DraftService) {}

  ngOnInit(): void {
    this.loadDrafts();
  }

  loadDrafts(): void {
    this.draftService.getDrafts().subscribe({
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

    alert('Draft copied.');
  }

  approveDraft(id: string): void {
    this.draftService.approveDraft(id).subscribe({
      next: () => {
        this.snackBar.open(
          'Draft Approved',

          'Close',

          {
            duration: 2500,
          },
        );
        this.loadDrafts();
      },

      error: (err: any) => {
        console.error(err);

        alert('Unable to approve draft.');
      },
    });
  }

  sendDraft(id: string): void {
    this.draftService.sendDraft(id).subscribe({
      next: () => {
        alert('Email Sent Successfully');

        this.loadDrafts();
      },

      error: (err: any) => {
        console.error(err);

        alert(err?.error?.detail || 'Failed to send email.');
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
        alert('Draft Updated');

        this.loadDrafts();
      },

      error: (err: any) => {
        console.error(err);

        alert('Unable to update draft.');
      },
    });
  }
}
