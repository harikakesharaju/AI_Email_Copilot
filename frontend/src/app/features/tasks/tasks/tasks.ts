import { Component, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';

import { MatCardModule } from '@angular/material/card';
import { MatCheckboxModule } from '@angular/material/checkbox';
import { MatChipsModule } from '@angular/material/chips';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatIconModule } from '@angular/material/icon';

import { TaskService } from '../../../core/services/task.service';
import { Task } from '../../../core/models/task.model';
import { finalize } from 'rxjs/operators';

@Component({
  selector: 'app-tasks',
  standalone: true,
  imports: [
    CommonModule,
    MatCardModule,
    MatCheckboxModule,
    MatChipsModule,
    MatProgressSpinnerModule,
    MatIconModule,
  ],
  templateUrl: './tasks.html',
  styleUrl: './tasks.css',
})
export class Tasks implements OnInit {

  tasks = signal<Task[]>([]);
  loading = signal(true);

  constructor(private taskService: TaskService) {}

  ngOnInit(): void {
    this.loadTasks();
  }

  loadTasks(): void {
    this.loading.set(true);

    this.taskService
      .getTasks()
      .pipe(
        finalize(() => {
          this.loading.set(false);
        })
      )
      .subscribe({
        next: (data: Task[]) => {
          this.tasks.set(data ?? []);
        },
        error: (err) => {
          console.error('Failed to load tasks:', err);
          this.tasks.set([]);
        },
      });
  }

  completeTask(taskId: string): void {
    this.taskService.completeTask(taskId).subscribe({
      next: () => {
        this.tasks.update(tasks =>
          tasks.filter(task => task.id !== taskId)
        );
      },
      error: (err) => {
        console.error('Failed to complete task:', err);
      },
    });
  }

  tasksWithDeadline(): number {
    return this.tasks().filter(task => !!task.deadline).length;
  }

  tasksWithoutDeadline(): number {
    return this.tasks().filter(task => !task.deadline).length;
  }

  isOverdue(task: Task): boolean {
    if (!task.deadline) {
      return false;
    }

    return new Date(task.deadline) < new Date();
  }
}