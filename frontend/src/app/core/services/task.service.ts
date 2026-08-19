import { Injectable } from '@angular/core';
import { Observable } from 'rxjs';

import { ApiService } from './api.service';
import { Task } from '../models/task.model';

@Injectable({
  providedIn: 'root'
})
export class TaskService {

  constructor(private api: ApiService) {}

  getTasks(): Observable<Task[]> {
    return this.api.get<Task[]>('/api/tasks');
  }

  completeTask(id: string): Observable<any> {
    return this.api.post(`/api/tasks/${id}/complete`, {});
  }

}