import dayjs from 'dayjs'

export const formatDateTime = (value: string | number | Date, template = 'YYYY-MM-DD HH:mm') =>
  dayjs(value).format(template)

export const formatDate = (value: string | number | Date, template = 'YYYY-MM-DD') =>
  dayjs(value).format(template)

export const formatNumber = (value: number, digits = 2) => value.toFixed(digits)

export const formatPercent = (value: number, digits = 2) => `${(value * 100).toFixed(digits)}%`
