export const isRequired = (value: string) => value.trim().length > 0

export const minLength = (value: string, length: number) => value.trim().length >= length

export const maxLength = (value: string, length: number) => value.trim().length <= length

export const isEmail = (value: string) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)
