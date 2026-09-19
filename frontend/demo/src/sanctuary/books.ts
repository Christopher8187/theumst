export interface Passage { title: string; kind: string; text: string; math?: string; answer?: string }
export interface BookSection { section_id:number; parent_section:number|null; section_number:string; section_name:string; is_book_root?:boolean }
export interface SampleBook {
  id: string; title: string; short: string; subject: string; color: string;
  symbol: string; count: number; edition: string; summary: string;
  passages: Passage[];
  publisher?:string; isbn?:string; version?:string; completed?:number; contents?:BookSection[];
}
