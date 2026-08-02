import { Injectable } from '@angular/core';
import { Observable } from 'rxjs';

import { ApiService } from './api.service';
import { Draft } from '../models/draft.model';


@Injectable({
  providedIn: 'root'
})
export class DraftService {

  constructor(private api: ApiService) {}

  getDrafts(): Observable<Draft[]> {

    return this.api.get<Draft[]>('/api/drafts');

  }

  approveDraft(id:string):Observable<any>{

  return this.api.post(`/api/drafts/${id}/approve`,{});

}

sendDraft(id:string):Observable<any>{

  return this.api.post(`/api/drafts/${id}/send`,{});

}

editDraft(id:string,newText:string):Observable<any>{

  return this.api.post(

    `/api/drafts/${id}/edit?new_text=${encodeURIComponent(newText)}`,

    {}

  );

}
}