import { Component, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';

import { MatCardModule } from '@angular/material/card';
import { MatCheckboxModule } from '@angular/material/checkbox';
import { MatChipsModule } from '@angular/material/chips';

import { TaskService } from '../../../core/services/task.service';
import { Task } from '../../../core/models/task.model';

@Component({

  selector: 'app-tasks',

  standalone: true,

  imports: [

    CommonModule,

    MatCardModule,

    MatCheckboxModule,

    MatChipsModule

  ],

  templateUrl: './tasks.html',

  styleUrl: './tasks.css'

})

export class Tasks implements OnInit {

  tasks = signal<Task[]>([]);

  constructor(private taskService: TaskService) {}

  ngOnInit(): void {

    this.taskService.getTasks().subscribe({

      next: data => {

        this.tasks.set(data);

      },

      error: err => console.error(err)

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