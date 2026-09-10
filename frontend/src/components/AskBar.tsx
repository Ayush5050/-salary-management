/**
 * Ask a question in plain English.
 *
 * The interaction is deliberately not "type a question, read an answer". The
 * question is translated into a filter selection, the translation is shown back
 * in plain English, and the ordinary dashboard re-renders under it. So the
 * answer arrives with its own working shown, and the HR Manager can adjust any
 * part of it with the normal filter controls.
 *
 * That matters more here than anywhere else in the app: a compensation figure
 * produced by a misread question looks exactly like a correct one.
 */

import { Alert, Button, Card, Group, Text, TextInput } from '@mantine/core'
import { IconAlertTriangle, IconSparkles } from '@tabler/icons-react'
import { useState } from 'react'

import { useAskQuestion } from '../api/queries'
import type { BreakdownDimension } from '../api/types'

interface AskBarProps {
  onApply: (queryString: string, dimension: BreakdownDimension | null) => void
}

const EXAMPLES = [
  'What do we pay engineering in Germany?',
  'Who earns more than $200k?',
  'Compensation by level',
] as const

export function AskBar({ onApply }: AskBarProps) {
  const [question, setQuestion] = useState('')
  const ask = useAskQuestion()

  const submit = async (text: string) => {
    if (text.trim() === '') return
    const parsed = await ask.mutateAsync(text)
    onApply(parsed.query_string, parsed.dimension)
  }

  return (
    <Card withBorder padding="md" mb="lg">
      <Group gap="sm" align="flex-end" wrap="nowrap">
        <TextInput
          flex={1}
          label="Ask a question"
          description="Plain English — the filters below update to match"
          placeholder={EXAMPLES[0]}
          leftSection={<IconSparkles size={16} />}
          value={question}
          onChange={(event) => setQuestion(event.currentTarget.value)}
          onKeyDown={(event) => {
            if (event.key === 'Enter') void submit(question)
          }}
        />
        <Button onClick={() => void submit(question)} loading={ask.isPending}>
          Ask
        </Button>
      </Group>

      {ask.data === undefined && ask.error === null && (
        <Group gap={6} mt="xs">
          <Text size="xs" c="dimmed">
            Try:
          </Text>
          {EXAMPLES.map((example) => (
            <Text
              key={example}
              size="xs"
              c="indigo"
              style={{ cursor: 'pointer' }}
              onClick={() => {
                setQuestion(example)
                void submit(example)
              }}
            >
              {example}
            </Text>
          ))}
        </Group>
      )}

      {ask.error !== null && (
        <Alert color="red" icon={<IconAlertTriangle size={16} />} mt="sm" p="xs">
          {ask.error.message}
        </Alert>
      )}

      {ask.data !== undefined && (
        <Alert
          color={ask.data.understood ? 'indigo' : 'yellow'}
          mt="sm"
          p="xs"
          title={ask.data.understood ? 'Showing' : 'Not sure what you meant'}
        >
          <Text size="sm">{ask.data.interpretation}</Text>
          {ask.data.unrecognised_terms.length > 0 && (
            // Named explicitly rather than quietly dropped: a half-understood
            // question must not look like a confident answer.
            <Text size="xs" c="dimmed" mt={4}>
              Ignored: {ask.data.unrecognised_terms.join(', ')}
            </Text>
          )}
        </Alert>
      )}
    </Card>
  )
}
