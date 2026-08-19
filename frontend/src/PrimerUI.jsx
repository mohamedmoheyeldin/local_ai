import { Button, FormControl, Heading, Label, Text } from '@primer/react'

export function SectionHeading({ title, description, actions }) {
  return <div className="section-heading"><div><Heading as="h2">{title}</Heading>{description && <Text as="p">{description}</Text>}</div>{actions && <div className="data-card-actions">{actions}</div>}</div>
}

export function Field({ label, caption, required, children, className = '' }) {
  return <FormControl required={required} className={className}><FormControl.Label>{label}</FormControl.Label>{children}{caption && <FormControl.Caption>{caption}</FormControl.Caption>}</FormControl>
}

export function EmptyState({ title, description }) {
  return <div className="empty-state"><strong>{title}</strong>{description && <span>{description}</span>}</div>
}

export function DataCard({ title, label, meta, detail, actions, status }) {
  return <article className="data-card"><div className="data-card-main"><div className="data-card-title">{status && <span className={`status-indicator ${status}`}></span>}<strong>{title}</strong>{label && <Label variant="secondary">{label}</Label>}</div>{meta && <span>{meta}</span>}{detail && <small>{detail}</small>}</div>{actions && <div className="data-card-actions">{actions}</div>}</article>
}

export function SubsectionHeading({ title, description }) {
  return <div className="subsection-heading"><Heading as="h3">{title}</Heading>{description && <Text as="p">{description}</Text>}</div>
}

export function DeleteButton({ children = 'Remove', ...props }) { return <Button variant="danger" size="small" {...props}>{children}</Button> }
export function FormActions({ children }) { return <div className="form-actions">{children}</div> }
export function MetricCard({ label, value }) { return <div className="metric-card"><Text as="span">{label}</Text><strong>{value}</strong></div> }
