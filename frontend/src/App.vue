<script setup lang="ts">
import { ConfigProvider, theme } from 'ant-design-vue'
import zhCN from 'ant-design-vue/es/locale/zh_CN'

const tokens = {
  algorithm: theme.darkAlgorithm,
  token: {
    colorPrimary: '#2dd4bf',
    colorInfo: '#2dd4bf',
    colorSuccess: '#34d399',
    colorWarning: '#f5a524',
    colorError: '#fb7185',
    colorBgBase: '#071016',
    colorBgContainer: '#121a22',
    colorBgElevated: '#16222c',
    colorBorder: 'rgba(125, 211, 201, 0.18)',
    colorText: '#e8f1f4',
    colorTextSecondary: '#8aa0ab',
    borderRadius: 10,
    fontFamily: `'IBM Plex Sans', 'PingFang SC', 'Noto Sans SC', sans-serif`,
  },
}
</script>

<template>
  <ConfigProvider :locale="zhCN" :theme="tokens">
    <router-view />
  </ConfigProvider>
</template>
