import { Injectable } from '@angular/core';
import { Observable } from 'rxjs';

import { ApiService } from './api.service';
import { Email } from '../models/email.model';

@Injectable({
  providedIn: 'root'
})
export class EmailService {

  constructor(private api: ApiService) {}

  getEmails(): Observable<Email[]> {

    return this.api.get<Email[]>('/api/emails');

  }

}