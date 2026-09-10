import { AppShell, Group, NavLink, Text, Title } from '@mantine/core'
import { IconChartBar, IconUsers } from '@tabler/icons-react'
import { Link, Navigate, Route, Routes, useLocation } from 'react-router-dom'

import { DashboardPage } from './pages/DashboardPage'
import { EmployeesPage } from './pages/EmployeesPage'

const NAV_ITEMS = [
  { to: '/dashboard', label: 'Dashboard', icon: IconChartBar },
  { to: '/employees', label: 'Employees', icon: IconUsers },
] as const

export function App() {
  const location = useLocation()

  return (
    <AppShell header={{ height: 60 }} navbar={{ width: 220, breakpoint: 'sm' }} padding="lg">
      <AppShell.Header>
        <Group h="100%" px="lg" justify="space-between">
          <Group gap="xs">
            <Title order={4}>ACME</Title>
            <Text c="dimmed" size="sm">
              Salary Management
            </Text>
          </Group>
          <Text c="dimmed" size="sm">
            Signed in as HR Manager
          </Text>
        </Group>
      </AppShell.Header>

      <AppShell.Navbar p="sm">
        {NAV_ITEMS.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            component={Link}
            // Navigation preserves the current filter selection, so moving
            // between the dashboard and the list keeps the same population in
            // view instead of silently resetting it.
            to={{ pathname: to, search: location.search }}
            label={label}
            leftSection={<Icon size={18} stroke={1.6} />}
            active={location.pathname === to}
          />
        ))}
      </AppShell.Navbar>

      <AppShell.Main>
        <Routes>
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/employees" element={<EmployeesPage />} />
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </AppShell.Main>
    </AppShell>
  )
}
