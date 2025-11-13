import { defineConfig } from 'vitepress'

// https://vitepress.dev/reference/site-config
export default defineConfig({
  title: "LFSS",
  description: "LFSS Documentation",
  base: '/.docs/',
  themeConfig: {
    // https://vitepress.dev/reference/default-theme-config
    nav: [
      { text: 'Home', link: '/' },
    ],

    sidebar: [
      {
        text: 'Quick Start',
        items: [
          { text: 'Server Setup', link: '/server-intro' },
          { text: 'Client Intro', link: '/client-intro' }, 
        ]
      }, 
      {
        text: 'Documentation',
        items: [
          { text: 'CLI Commands', link: '/commands' },
          { text: 'Environment Variables', link: '/environment-variables' },
          { text: 'Permission System', link: '/permission' },
          { text: 'User Management', link: '/userman' },
          { text: 'Virtual User', link: '/virtual-user' },
          { text: 'Configure Single Directory', link: '/lfssdir' },
          { text: 'WebDAV', link: '/webdav' },
          { text: 'Development', link: '/Development' },
        ]
      }, 
      {
        text: 'About',
        items: [
          { text: 'Changelogs', link: '/changelogs' },
        ]
      }
    ],

    socialLinks: [
      { icon: 'github', link: 'https://github.com/menxli/lfss' }
    ]
  }
})
