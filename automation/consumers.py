import json
import os
from channels.generic.websocket import AsyncWebsocketConsumer
from asgiref.sync import sync_to_async
from django.conf import settings
from .models import ScrapingTask
import asyncio

def get_log_file_path(task_id):
    return os.path.join(settings.MEDIA_ROOT, f'task_logs_{task_id}.txt')


class LogConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.task_id = self.scope['url_route']['kwargs']['task_id']
        self.task_group_name = f'task_{self.task_id}'

        # Join task group
        await self.channel_layer.group_add(
            self.task_group_name,
            self.channel_name
        )

        await self.accept()

        # Start sending logs
        asyncio.create_task(self.send_logs())

        # Start periodic status updates
        self.status_update_task = asyncio.create_task(self.periodic_status_update())

    async def disconnect(self, close_code):
        # Leave task group
        await self.channel_layer.group_discard(
            self.task_group_name,
            self.channel_name
        )
        if hasattr(self, 'status_update_task'):
            self.status_update_task.cancel()

    async def send_logs(self):
        while True:
            task = await sync_to_async(ScrapingTask.objects.get)(id=self.task_id)
            if task.status in ['COMPLETED', 'FAILED']:
                break

            logs = await self.get_latest_logs(task)
            if logs:
                await self.send(text_data=json.dumps({
                    'logs': logs
                }))

            await asyncio.sleep(1)  # Wait for 1 second before checking again

    @sync_to_async
    def get_latest_logs(self, task):
        log_file_path = get_log_file_path(task.id)
        if not os.path.exists(log_file_path):
            return ""
        
        with open(log_file_path, 'r') as file:
            file.seek(0, 2)  # Move to the end of the file
            if file.tell() > 1024 * 100:  # If file is larger than 100KB
                file.seek(-1024 * 100, 2)  # Move 100KB back from the end
            else:
                file.seek(0)
            return file.read()
    
    async def receive(self, text_data):
        pass

    async def periodic_status_update(self):
        while True:
            await asyncio.sleep(5)  # Update every 5 seconds
            task = await self.get_task()
            await self.send_status_update(task.status)

    async def send_status_update(self, status):
        await self.send(text_data=json.dumps({
            'type': 'status_update',
            'status': status
        }))

    @sync_to_async
    def get_task(self):
        return ScrapingTask.objects.get(id=self.task_id)