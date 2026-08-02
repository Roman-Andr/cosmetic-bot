export type NoticeTone = "error" | "success";

export type NoticeHandler = (message: string | null, tone?: NoticeTone) => void;
