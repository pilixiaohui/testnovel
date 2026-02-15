import { beforeEach, describe, expect, it, vi } from 'vitest'

const requestUseMock = vi.hoisted(() => vi.fn())
const responseUseMock = vi.hoisted(() => vi.fn())
const axiosCreateMock = vi.hoisted(() =>
  vi.fn(() => ({
    interceptors: {
      request: { use: requestUseMock },
      response: { use: responseUseMock },
    },
  })),
)
const messageErrorMock = vi.hoisted(() => vi.fn())

vi.mock('axios', () => ({
  default: {
    create: axiosCreateMock,
  },
}))

vi.mock('element-plus', () => ({
  ElMessage: {
    error: messageErrorMock,
  },
}))

describe('api client error handling', () => {
  beforeEach(() => {
    vi.resetModules()
    requestUseMock.mockReset()
    responseUseMock.mockReset()
    messageErrorMock.mockReset()
    axiosCreateMock.mockClear()
  })

  it('normalizes non-string detail before showing error message', async () => {
    await import('@/api/index')

    expect(responseUseMock).toHaveBeenCalledTimes(1)
    const onRejected = responseUseMock.mock.calls[0][1] as (error: unknown) => Promise<never>
    const error = {
      response: {
        data: {
          detail: [
            {
              loc: ['body', 'root', 0],
              msg: 'invalid scene payload',
            },
          ],
        },
      },
    }

    await expect(onRejected(error)).rejects.toBe(error)
    expect(messageErrorMock).toHaveBeenCalledWith(
      '[{"loc":["body","root",0],"msg":"invalid scene payload"}]',
    )
  })
})
