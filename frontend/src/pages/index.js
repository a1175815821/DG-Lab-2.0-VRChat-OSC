import Head from 'next/head';
import { Box, Container, Unstable_Grid2 as Grid } from '@mui/material';
import { Layout as DashboardLayout } from 'src/layouts/dashboard/layout';
import { OverviewCoyote } from 'src/sections/overview/overview-coyote';
import { OverviewOscStatus } from 'src/sections/overview/overview-osc-status';
import { OverviewSafeMode } from 'src/sections/overview/overview-safe-mode';
import { OverviewVRC } from 'src/sections/overview/overview-vrc';

const Page = () => (
  <>
    <Head>
      <title>
        总览 | OSC Toys
      </title>
    </Head>
    <Box
      component="main"
      sx={{
        flexGrow: 1,
        py: 8
      }}
    >
      <Container maxWidth="xl">
        <Grid
          container
          spacing={3}
        >
          <Grid
            xs={12}
            sm={6}
            lg={3}
          >
            <OverviewCoyote
              sx={{ height: '100%' }}
            />
          </Grid>

          <Grid
            xs={12}
            sm={6}
            lg={3}
          >
            <OverviewSafeMode
              sx={{ height: '100%' }}
            />
          </Grid>

          {/* OSC 链接状态卡片：放在安全模式和 VRC 之间，显示参数情况 */}
          <Grid
            xs={12}
            lg={6}
          >
            <OverviewOscStatus
              sx={{ height: '100%' }}
            />
          </Grid>

          <Grid
            xs={12}
            lg={12}
          >
            <OverviewVRC />
          </Grid>

        </Grid>
      </Container>
    </Box>
  </>
);

Page.getLayout = (page) => (
  <DashboardLayout>
    {page}
  </DashboardLayout>
);

export default Page;
