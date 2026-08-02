import { formatAmount } from "../lib/format";
import { cn } from "../lib/cn";
import { ui } from "./classes";

export function CurrencySymbol({ className = "" }: { className?: string }) {
  return <span className={cn(ui("currency-symbol"), className)} aria-hidden="true" />;
}

export function Money({ value, prefix = "", className = "" }: { value: string | number; prefix?: string; className?: string }) {
  return <span className={cn(ui("money"), className)} aria-label={`${prefix}${formatAmount(value)} белорусских рублей`}><span>{prefix}{formatAmount(value)}</span><CurrencySymbol /></span>;
}
