/**
 * Presentational primitives. No data fetching, no domain knowledge — everything
 * here is styled purely from the tokens in `styles/globals.css`.
 */
import type { ButtonHTMLAttributes, ReactNode, TextareaHTMLAttributes } from 'react'
import type { InputHTMLAttributes } from 'react'

type Variant = 'default' | 'primary' | 'danger' | 'ghost'

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant
  size?: 'sm' | 'md'
  block?: boolean
  loading?: boolean
}

export function Button({
  variant = 'default',
  size = 'md',
  block,
  loading,
  disabled,
  children,
  className = '',
  ...rest
}: ButtonProps) {
  const classes = [
    'btn',
    variant !== 'default' ? `btn--${variant}` : '',
    size === 'sm' ? 'btn--sm' : '',
    block ? 'btn--block' : '',
    className,
  ]
    .filter(Boolean)
    .join(' ')

  return (
    <button className={classes} disabled={disabled || loading} {...rest}>
      {loading && <span className="spinner" aria-hidden />}
      {children}
    </button>
  )
}

interface FieldProps {
  label: string
  hint?: string
  children: ReactNode
}

export function Field({ label, hint, children }: FieldProps) {
  return (
    <label className="field">
      <span className="field__label">{label}</span>
      {children}
      {hint && <span className="field__hint">{hint}</span>}
    </label>
  )
}

export function Input(props: InputHTMLAttributes<HTMLInputElement>) {
  return <input {...props} className={`input ${props.className ?? ''}`} />
}

interface TextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  mono?: boolean
}

export function Textarea({ mono, className = '', ...rest }: TextareaProps) {
  return <textarea {...rest} className={`textarea ${mono ? 'textarea--mono' : ''} ${className}`} />
}

export function Card({
  title,
  children,
  className = '',
}: {
  title?: ReactNode
  children: ReactNode
  className?: string
}) {
  return (
    <div className={`card ${className}`}>
      {title && <div className="card__title">{title}</div>}
      {children}
    </div>
  )
}

export type Tone = 'neutral' | 'success' | 'warning' | 'danger' | 'info' | 'accent'

export function Badge({ tone = 'neutral', children }: { tone?: Tone; children: ReactNode }) {
  return (
    <span className={`badge ${tone !== 'neutral' ? `badge--${tone}` : ''}`}>{children}</span>
  )
}

export function Banner({
  tone,
  children,
}: {
  tone: 'danger' | 'warning' | 'success'
  children: ReactNode
}) {
  return (
    <div className={`banner banner--${tone}`} role="status">
      {children}
    </div>
  )
}

export function Empty({ children }: { children: ReactNode }) {
  return <div className="empty">{children}</div>
}

export function Spinner() {
  return <span className="spinner" role="status" aria-label="Loading" />
}

/** Renders a list of records as a scrollable table — used for calendars/plans. */
export function DataTable<T extends Record<string, unknown>>({
  rows,
  columns,
}: {
  rows: T[]
  columns: (keyof T & string)[]
}) {
  if (!rows.length) return <Empty>Nothing here yet.</Empty>
  return (
    <div className="table-wrap">
      <table className="data">
        <thead>
          <tr>
            {columns.map((c) => (
              <th key={c}>{c.replace(/_/g, ' ')}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i}>
              {columns.map((c) => {
                const v = r[c]
                return <td key={c}>{Array.isArray(v) ? v.join(', ') : String(v ?? '')}</td>
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
