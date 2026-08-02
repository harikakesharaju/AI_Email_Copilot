import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { MatCardModule } from '@angular/material/card';

import { EmailService } from '../../../core/services/email.service';
import { TaskService } from '../../../core/services/task.service';

import { Email } from '../../../core/models/email.model';
import { Task } from '../../../core/models/task.model';
import { ChangeDetectorRef } from '@angular/core';
import { signal } from '@angular/core';


@Component({

  selector: 'app-dashboard',

  standalone: true,

  imports: [
    CommonModule,
    MatCardModule
  ],

  templateUrl: './dashboard.html',

  styleUrl: './dashboard.css'

})
export class Dashboard implements OnInit {

emails = signal<Email[]>([]);

tasks = signal<Task[]>([]);
constructor(
  private emailService: EmailService,
  private taskService: TaskService,
  private cdr: ChangeDetectorRef
) {}

  ngOnInit(): void {

    this.loadDashboard();

  }

  loadDashboard() {

    this.emailService.getEmails().subscribe({

      next: (data) => {
        this.emails.set(data);
        console.log("Emails received:", data);

      },

      error: (err) => console.error(err)

    });

    this.taskService.getTasks().subscribe({

      next: (data) => {
        this.tasks.set(data);
        console.log("Tasks received:", data);

      },

      error: (err) => console.error(err)

    });

  }

}