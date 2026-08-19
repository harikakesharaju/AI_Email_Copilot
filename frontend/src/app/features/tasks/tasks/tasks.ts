import { Component, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';

import { MatCardModule } from '@angular/material/card';
import { MatCheckboxModule } from '@angular/material/checkbox';
import { MatChipsModule } from '@angular/material/chips';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatIconModule } from '@angular/material/icon';

import { TaskService } from '../../../core/services/task.service';
import { finalize } from 'rxjs/operators';
import { Task } from '../../../core/models/task.model';

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

  styleUrl: './tasks.css'

})

export class Tasks implements OnInit {

  tasks = signal<Task[]>([]);
  loading = true;

  constructor(private taskService: TaskService) {}

  ngOnInit(): void {
    this.loadTasks();
  }

  loadTasks(): void {
    this.loading = true;
    this.taskService.getTasks().pipe(
      finalize(() => { this.loading = false; })
    ).subscribe({
      next: data => {
        this.tasks.set(data);
      },
      error: err => {
        console.error(err);
      }
    });
  }

  completeTask(taskId: string): void {
    this.taskService.completeTask(taskId).subscribe({
      next: () => {
        this.tasks.update(tasks => tasks.filter(t => t.id !== taskId));
      },
      error: err => console.error(err),
    });
  }

  tasksWithDeadline(): number {

    return this.tasks()
        .filter(t => t.deadline)
        .length;

}

tasksWithoutDeadline(): number {

    return this.tasks()
        .filter(t => !t.deadline)
        .length;

}

isOverdue(task: Task): boolean {

    if(!task.deadline) return false;

    return new Date(task.deadline) < new Date();

}

}