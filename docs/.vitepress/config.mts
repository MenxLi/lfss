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
        text: 'Documentation',
        items: [
          { text: 'Getting Started', link: '/getting-started' },
          { text: 'Environment Variables', link: '/environment-variables' },
          { text: 'Client Intro', link: '/client-intro' }, 
          { text: 'Permission System', link: '/permission' },
          { text: 'WebDAV', link: '/webdav' },
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
